"""Self-entry upsert for a manual daily record. There is no bulk path and
no identity resolution here - the record's owner is always whoever is
logged in and submitting it (see the module's design doc, §4).
"""
from datetime import datetime, timezone

from app.extensions import db
from app.manual_daily_records.models import ManualDailyRecord

_ENTRY_FIELDS = (
    "tech_issues_downtime_hours",
    "no_inventory_idle_time_hours",
    "leave_hours",
    "meeting_engagement_hours",
)


def upsert_own_record(user_id, data):
    """Creates today's-or-any-day's record for `user_id`, or updates it if
    one already exists for that (user, date) pair - unique per §6.1, so
    re-submitting the same day always edits in place rather than creating
    a duplicate.

    Any edit - whether the record was previously Pending, Approved, or
    Rejected - resets it to Pending and clears the prior review: an
    approval or rejection was a decision about these exact numbers, and
    that decision no longer applies once the numbers change (§6.3, applied
    symmetrically to rejection per §9's resubmission assumption).
    """
    record = ManualDailyRecord.query.filter_by(user_id=user_id, record_date=data["record_date"]).first()
    if record is None:
        record = ManualDailyRecord(user_id=user_id, record_date=data["record_date"])
        db.session.add(record)

    pvp_count = data.get("pvp_count")
    foundation_count = data.get("foundation_count")
    if pvp_count is None and foundation_count is None:
        pvp_count, foundation_count = data.get("production_count", 0), 0
    record.pvp_count = pvp_count or 0
    record.foundation_count = foundation_count or 0
    record.production_count = record.pvp_count + record.foundation_count

    for field in _ENTRY_FIELDS:
        setattr(record, field, data[field])

    record.status = "pending"
    record.reviewed_by_id = None
    record.reviewed_at = None
    record.rejection_reason = None

    db.session.commit()

    # A user's first real production day is the authoritative M1 start for
    # future cohorts. Recompute from live facts so a lead and an employee
    # progress identically and no scheduled refresh is required.
    if record.production_count > 0:
        from app.cohorts.models import CohortMembership
        from app.cohorts.services import compute_user_stage_periods

        membership = CohortMembership.query.filter_by(user_id=user_id).first()
        if membership is not None:
            compute_user_stage_periods(membership)
            db.session.commit()
    return record


def approve_record(record, reviewed_by_id):
    """Mutates `record` in place to Approved - does not commit, so a caller
    reviewing several records (the Reports dashboard's bulk-approve) can
    apply this to each one and commit exactly once."""
    record.status = "approved"
    record.reviewed_by_id = reviewed_by_id
    record.reviewed_at = datetime.now(timezone.utc)
    record.rejection_reason = None


def reject_record(record, reviewed_by_id, reason=None):
    """Mutates `record` in place to Rejected - see approve_record() re: no commit."""
    record.status = "rejected"
    record.reviewed_by_id = reviewed_by_id
    record.reviewed_at = datetime.now(timezone.utc)
    record.rejection_reason = reason
