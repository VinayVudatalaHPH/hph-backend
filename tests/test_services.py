import datetime as dt

from app.cohorts.models import (
    Coder,
    CohortJoinReview,
    CoderStagePeriod,
    Cohort,
    ManualProductionFact,
    StageException,
    StageTargetRule,
)
from app.cohorts.services import assign_cohort, compute_stage_periods, get_daily_target, overlapping_rule_exists
from app.extensions import db


def _make_coder(full_name, join_date, cohort_id=None):
    coder = Coder(full_name=full_name, join_date=join_date, cohort_id=cohort_id)
    db.session.add(coder)
    db.session.flush()
    return coder


def test_compute_stage_periods_normal_ramp_coder():
    """A coder with real activity gets the full Training->Steady State
    cascade, M1 anchored to their first real chart, everything after it a
    pure calendar offset.
    """
    coder = _make_coder("Test Coder Normal", dt.date(2026, 1, 1))
    db.session.add(
        ManualProductionFact(coder_id=coder.id, activity_date=dt.date(2026, 1, 5), production_count=3)
    )
    db.session.commit()

    periods = {p.stage_code: p for p in compute_stage_periods(coder)}

    assert periods["Training"].start_date == dt.date(2026, 1, 1)
    assert periods["Training"].end_date == dt.date(2026, 1, 4)
    assert periods["Training"].source == "observed_first_activity"

    assert periods["M1"].start_date == dt.date(2026, 1, 5)
    assert periods["M1"].end_date == dt.date(2026, 2, 3)  # 30 days
    assert periods["M1"].source == "calendar_offset"

    assert periods["M2"].start_date == dt.date(2026, 2, 4)
    assert periods["M3"].start_date == periods["M2"].end_date + dt.timedelta(days=1)
    assert periods["M4"].start_date == periods["M3"].end_date + dt.timedelta(days=1)
    assert periods["Steady State"].start_date == periods["M4"].end_date + dt.timedelta(days=1)
    assert periods["Steady State"].end_date is None


def test_compute_stage_periods_no_activity_yet():
    """A brand-new coder with no manual/Kairon activity yet stays in an
    open-ended Training - nothing downstream is invented.
    """
    coder = _make_coder("Test Coder Mid Training", dt.date(2026, 2, 1))

    periods = compute_stage_periods(coder)

    assert len(periods) == 1
    assert periods[0].stage_code == "Training"
    assert periods[0].start_date == dt.date(2026, 2, 1)
    assert periods[0].end_date is None


def test_compute_stage_periods_exception_shifts_only_that_coder(superadmin):
    """An exception on one coder's Training pushes their own M1+ schedule
    later by the same amount, and does not touch a peer who started on the
    exact same day with no exception of their own.
    """
    coder_a = _make_coder("Test Coder Exception", dt.date(2026, 1, 1))
    coder_b = _make_coder("Test Coder No Exception", dt.date(2026, 1, 1))
    for coder in (coder_a, coder_b):
        db.session.add(
            ManualProductionFact(coder_id=coder.id, activity_date=dt.date(2026, 1, 15), production_count=2)
        )
    db.session.add(
        StageException(
            coder_id=coder_a.id,
            stage_code="Training",
            extra_days=14,
            reason="needs two more weeks",
            created_by_id=superadmin.id,
        )
    )
    db.session.commit()

    periods_a = {p.stage_code: p for p in compute_stage_periods(coder_a)}
    periods_b = {p.stage_code: p for p in compute_stage_periods(coder_b)}

    assert periods_a["Training"].end_date == dt.date(2026, 1, 14) + dt.timedelta(days=14)
    assert periods_a["M1"].start_date == periods_a["Training"].end_date + dt.timedelta(days=1)
    assert periods_a["M1"].shifted_by_exception_days == 14

    assert periods_b["Training"].end_date == dt.date(2026, 1, 14)
    assert periods_b["M1"].start_date == dt.date(2026, 1, 15)
    assert periods_b["M1"].shifted_by_exception_days == 0


def test_get_daily_target_resolves_stage_and_rule():
    """Exercises the same lookup a tenured/BAU coder relies on - a coder
    with just a single (Steady State) period still resolves a target
    through the normal stage->rule join, using the real seeded rule.
    """
    coder = _make_coder("Test Coder Tenured", dt.date(2020, 1, 1))
    db.session.add(
        CoderStagePeriod(
            coder_id=coder.id,
            stage_code="Steady State",
            start_date=dt.date(2020, 1, 1),
            end_date=None,
            source="manual_override",
            shifted_by_exception_days=0,
        )
    )
    db.session.commit()

    assert get_daily_target(coder, dt.date(2026, 3, 1)) == 30  # seeded Steady State rule
    assert get_daily_target(coder, dt.date(2019, 12, 31)) is None  # before this coder's only period


def test_assign_cohort_direct_when_unambiguous():
    cohort = Cohort(sequence_no=1, label="Only Open Cohort", window_start=dt.date(2026, 6, 1))
    db.session.add(cohort)
    db.session.flush()

    coder = _make_coder("Test Coder Clear Join", dt.date(2026, 6, 2))
    assign_cohort(coder)

    assert coder.cohort_id == cohort.id
    assert CohortJoinReview.query.filter_by(coder_id=coder.id).count() == 0


def test_assign_cohort_flags_ambiguous_join_instead_of_guessing():
    current = Cohort(sequence_no=2, label="Current Open Cohort", window_start=dt.date(2026, 6, 1))
    nearby = Cohort(sequence_no=1, label="Nearby Prior Cohort", window_start=dt.date(2026, 5, 25))
    db.session.add_all([current, nearby])
    db.session.flush()

    coder = _make_coder("Test Coder Ambiguous Join", dt.date(2026, 5, 28))
    assign_cohort(coder)

    assert coder.cohort_id is None
    review = CohortJoinReview.query.filter_by(coder_id=coder.id).one()
    assert review.status == "pending"
    assert set(review.candidate_cohort_ids) == {current.id, nearby.id}


def test_overlapping_rule_exists(superadmin):
    StageTargetRule.query.filter_by(stage_code="M1").delete()
    db.session.add(
        StageTargetRule(
            stage_code="M1",
            effective_from=dt.date(2020, 1, 1),
            effective_to=dt.date(2020, 6, 1),
            daily_target=5,
            created_by_id=superadmin.id,
        )
    )
    db.session.commit()

    assert overlapping_rule_exists("M1", dt.date(2020, 3, 1), None) is True
    assert overlapping_rule_exists("M1", dt.date(2020, 6, 1), None) is False  # half-open: touching, not overlapping
    assert overlapping_rule_exists("M1", dt.date(2021, 1, 1), None) is False
