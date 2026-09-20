"""Aggregation/read layer for the personal Reports view and the Coding
project dashboard - no new source-of-truth tables, everything here reads
or updates rows already owned by app.kairon and app.manual_daily_records.
"""
import calendar
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from flask_smorest import abort
from sqlalchemy import case, func

from app.cohorts.models import Cohort, CohortMembership, StageTargetRule, UserStagePeriod
from app.extensions import db
from app.kairon.models import KaironChartRecord, KaironUploadBatch
from app.login_hours.models import LoginHourRecord
from app.manual_daily_records.models import ManualDailyRecord
from app.manual_daily_records.services import approve_record, reject_record
from app.roles.models import Role, RoleType
from app.users.models import Project, User


FULL_WORKDAY_MINUTES = 8 * 60
EFFICIENCY_CAP_PERCENT = Decimal("120.0")


def _hours_to_minutes(value):
    return int((Decimal(value or 0) * 60).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _percent(actual, target):
    if target <= 0:
        return None
    raw = Decimal(actual) * 100 / target
    return min(raw, EFFICIENCY_CAP_PERCENT).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)


def _cpd(actual, effective_minutes):
    if effective_minutes is None or effective_minutes <= 0:
        return None
    return (Decimal(actual) * FULL_WORKDAY_MINUTES / effective_minutes).quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )


def _manual_count(record, program=None):
    if record is None:
        return 0
    if program == "PVP":
        return record.pvp_count
    if program == "FOUNDATION":
        return record.foundation_count
    return record.production_count


def get_efficiency(user_ids, from_date, to_date, include_daily=False, program=None):
    """Calculate daily and period efficiency from the existing source rows.

    A full-day stage target represents eight hours. Its adjustment is based
    on recorded downtime, idle, meetings, and leave/permission -- not small
    variations in actual login time. Productive time uses actual inside time
    less downtime, idle time, and meetings. CPD follows Daily Refresh and uses
    the standard eight-hour target basis after all exclusions. Displayed
    efficiency is capped at 120%; period metrics use weighted totals.
    """
    if not user_ids:
        return {}

    login_rows = LoginHourRecord.query.filter(
        LoginHourRecord.user_id.in_(user_ids),
        LoginHourRecord.attendance_date >= from_date,
        LoginHourRecord.attendance_date <= to_date,
    ).all()
    manual_rows = ManualDailyRecord.query.filter(
        ManualDailyRecord.user_id.in_(user_ids),
        ManualDailyRecord.record_date >= from_date,
        ManualDailyRecord.record_date <= to_date,
    ).all()
    kairon_query = (
        db.session.query(
            KaironChartRecord.user_id,
            KaironChartRecord.completed_date,
            func.count(KaironChartRecord.id),
        )
        .join(KaironUploadBatch, KaironChartRecord.batch_id == KaironUploadBatch.id)
        .filter(
            KaironUploadBatch.superseded_at.is_(None),
            KaironChartRecord.status == "Completed",
            KaironChartRecord.user_id.in_(user_ids),
            KaironChartRecord.completed_date >= from_date,
            KaironChartRecord.completed_date <= to_date,
        )
    )
    if program:
        kairon_query = kairon_query.filter(func.upper(KaironChartRecord.program) == program)
    kairon_rows = kairon_query.group_by(
        KaironChartRecord.user_id, KaironChartRecord.completed_date
    ).all()
    periods = UserStagePeriod.query.filter(
        UserStagePeriod.user_id.in_(user_ids),
        UserStagePeriod.start_date <= to_date,
        db.or_(UserStagePeriod.end_date.is_(None), UserStagePeriod.end_date >= from_date),
    ).all()
    rules = StageTargetRule.query.filter(
        StageTargetRule.effective_from <= to_date,
        db.or_(StageTargetRule.effective_to.is_(None), StageTargetRule.effective_to > from_date),
    ).all()

    login_by_key = {(row.user_id, row.attendance_date): row for row in login_rows}
    manual_by_key = {(row.user_id, row.record_date): row for row in manual_rows}
    kairon_by_key = {(user_id, completed_date): count for user_id, completed_date, count in kairon_rows}
    periods_by_user = {}
    for period in periods:
        periods_by_user.setdefault(period.user_id, []).append(period)
    rules_by_stage = {}
    for rule in rules:
        rules_by_stage.setdefault(rule.stage_code, []).append(rule)

    results = {}
    all_keys = set(login_by_key) | set(manual_by_key) | set(kairon_by_key)
    for user_id in user_ids:
        dates = sorted((day for uid, day in all_keys if uid == user_id), reverse=True)
        daily = []
        total_manual_charts = 0
        total_kairon_charts = 0
        total_adjusted_target = Decimal("0")
        total_target_minutes = 0
        total_inside_minutes = 0
        login_days = 0
        total_productive_minutes = 0
        calculated_days = 0

        for work_date in dates:
            login = login_by_key.get((user_id, work_date))
            manual = manual_by_key.get((user_id, work_date))
            period = next(
                (
                    item
                    for item in periods_by_user.get(user_id, [])
                    if item.start_date <= work_date and (item.end_date is None or item.end_date >= work_date)
                ),
                None,
            )
            rule = next(
                (
                    item
                    for item in rules_by_stage.get(period.stage_code if period else None, [])
                    if item.effective_from <= work_date
                    and (item.effective_to is None or item.effective_to > work_date)
                ),
                None,
            )

            inside_minutes = login.total_inside_minutes if login else None
            downtime_minutes = _hours_to_minutes(manual.tech_issues_downtime_hours) if manual else 0
            idle_minutes = _hours_to_minutes(manual.no_inventory_idle_time_hours) if manual else 0
            leave_minutes = _hours_to_minutes(manual.leave_hours) if manual else 0
            meeting_minutes = _hours_to_minutes(manual.meeting_engagement_hours) if manual else 0
            excluded_minutes = downtime_minutes + idle_minutes + leave_minutes + meeting_minutes
            operational_deduction_minutes = downtime_minutes + idle_minutes + meeting_minutes
            productive_minutes = (
                max(inside_minutes - operational_deduction_minutes, 0)
                if inside_minutes is not None
                else None
            )
            # Daily Refresh outer-merges Manual and Kairon by coder/date. Any
            # source row therefore receives the standard eight-hour target
            # capacity, reduced by manual exclusions when they exist. Login
            # data remains necessary only for actual productive time.
            has_source_row = manual is not None or (user_id, work_date) in kairon_by_key
            target_minutes = (
                max(FULL_WORKDAY_MINUTES - excluded_minutes, 0)
                if has_source_row
                else None
            )
            daily_target = rule.daily_target if rule else None
            adjusted_target = (
                (Decimal(daily_target) * target_minutes / FULL_WORKDAY_MINUTES).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
                if daily_target is not None and target_minutes is not None
                else None
            )
            manual_charts = _manual_count(manual, program)
            kairon_charts = kairon_by_key.get((user_id, work_date), 0)
            manual_efficiency_percent = (
                _percent(manual_charts, adjusted_target) if adjusted_target is not None else None
            )
            kairon_efficiency_percent = (
                _percent(kairon_charts, adjusted_target) if adjusted_target is not None else None
            )
            manual_cpd = _cpd(manual_charts, target_minutes)
            kairon_cpd = _cpd(kairon_charts, target_minutes)
            target_cpd = _cpd(adjusted_target, target_minutes) if adjusted_target is not None else None

            if has_source_row:
                total_manual_charts += manual_charts
                total_kairon_charts += kairon_charts
                total_target_minutes += target_minutes
                calculated_days += 1
            if adjusted_target is not None:
                total_adjusted_target += adjusted_target
            if inside_minutes is not None:
                total_inside_minutes += inside_minutes
                login_days += 1
            if productive_minutes is not None:
                total_productive_minutes += productive_minutes

            if include_daily:
                daily.append(
                    {
                        "date": work_date,
                        "stage": period.stage_code if period else None,
                        "daily_target": daily_target,
                        "manual_charts": manual_charts,
                        "kairon_charts": kairon_charts,
                        "inside_minutes": inside_minutes,
                        "downtime_minutes": downtime_minutes,
                        "idle_minutes": idle_minutes,
                        "leave_minutes": leave_minutes,
                        "meeting_minutes": meeting_minutes,
                        "excluded_minutes": excluded_minutes,
                        "productive_minutes": productive_minutes,
                        "target_minutes": target_minutes,
                        "adjusted_target": adjusted_target,
                        "manual_efficiency_percent": manual_efficiency_percent,
                        "kairon_efficiency_percent": kairon_efficiency_percent,
                        "manual_cpd": manual_cpd,
                        "kairon_cpd": kairon_cpd,
                        "target_cpd": target_cpd,
                        "manual_status": manual.status if manual else None,
                    }
                )

        results[user_id] = {
            "from_date": from_date,
            "to_date": to_date,
            "manual_charts": total_manual_charts,
            "kairon_charts": total_kairon_charts,
            "adjusted_target": total_adjusted_target.quantize(Decimal("0.01")),
            "inside_minutes": total_inside_minutes,
            "login_days": login_days,
            "productive_minutes": total_productive_minutes,
            "target_minutes": total_target_minutes,
            "calculated_days": calculated_days,
            "manual_efficiency_percent": _percent(total_manual_charts, total_adjusted_target),
            "kairon_efficiency_percent": _percent(total_kairon_charts, total_adjusted_target),
            "manual_cpd": _cpd(total_manual_charts, total_target_minutes),
            "kairon_cpd": _cpd(total_kairon_charts, total_target_minutes),
            "target_cpd": _cpd(total_adjusted_target, total_target_minutes),
            "daily": daily,
        }
    return results


def resolve_dashboard_window(args):
    """Turns the query args of GET /api/dashboards/coding into a concrete
    (from_date, to_date) pair.

    Precedence: an explicit from/to range wins, then a single `date`, then
    `month` and `year` shorthands. The current month/year is clipped to
    today. With no filters, the window is the 1st of the current month
    through today (§4.2's "rolling month-to-date").
    """
    today = date.today()

    if args.get("from_date") or args.get("to_date"):
        from_date = args.get("from_date") or args["to_date"]
        to_date = args.get("to_date") or args["from_date"]
        return from_date, to_date

    if args.get("date"):
        return args["date"], args["date"]

    if args.get("month"):
        try:
            year, month = (int(part) for part in args["month"].split("-"))
            first = date(year, month, 1)
        except ValueError:
            abort(400, message="month must be a valid 'YYYY-MM' value.")
        last = date(year, month, calendar.monthrange(year, month)[1])
        return first, min(last, today)

    if args.get("year"):
        year = args["year"]
        first = date(year, 1, 1)
        last = date(year, 12, 31)
        return first, min(last, today) if year == today.year else last

    return today.replace(day=1), today


def bulk_approve_manual_records(record_ids, reviewed_by_id):
    """Approves every id in `record_ids` that's currently pending, in one
    transaction. An id that doesn't exist or isn't pending is reported back
    in `skipped` rather than failing the whole batch - see the Reports
    doc's §3.3/§7 on why Accept All can't be all-or-nothing (the visible/
    filtered set it's applied to may include already-decided records,
    shown for audit).
    """
    approved, skipped = [], []
    for record_id in record_ids:
        record = db.session.get(ManualDailyRecord, record_id)
        if record is None:
            skipped.append({"id": record_id, "reason": "Record not found."})
        elif record.status != "pending":
            skipped.append({"id": record_id, "reason": "Record isn't pending review."})
        else:
            approve_record(record, reviewed_by_id)
            approved.append(record_id)

    db.session.commit()
    return {"approved": approved, "skipped": skipped}


def bulk_reject_manual_records(items, reviewed_by_id):
    """Same best-effort behavior as bulk_approve_manual_records(), but each
    item carries its own {id, reason} - rejection always needs a reason per
    record, never one shared across the batch.
    """
    rejected, skipped = [], []
    for item in items:
        record = db.session.get(ManualDailyRecord, item["id"])
        if record is None:
            skipped.append({"id": item["id"], "reason": "Record not found."})
        elif record.status != "pending":
            skipped.append({"id": item["id"], "reason": "Record isn't pending review."})
        else:
            reject_record(record, reviewed_by_id, item.get("reason"))
            rejected.append(item["id"])

    db.session.commit()
    return {"rejected": rejected, "skipped": skipped}


def get_coding_dashboard(from_date, to_date, program=None, lead_id=None, cohort_id=None, include_daily=False):
    """One card per active user for the given window (§4.4): Kairon chart
    counts include completed charts only, scoped by each chart's completed
    date. Manual production/hours/pending totals are scoped by each record's
    own record_date.
    """
    # The dashboard population is the operational coder definition, not
    # every active account in the application. Leads are production coders
    # too; their role only changes authorization/reporting hierarchy.
    users_query = (
        User.query.join(Role)
        .join(RoleType)
        .join(Project)
        .filter(
            User.is_active.is_(True),
            Project.name == "CODING",
            RoleType.code.in_(("lead", "employee")),
        )
    )
    if cohort_id is not None:
        if db.session.get(Cohort, cohort_id) is None:
            abort(400, message="cohortId must reference an existing cohort.")
        users_query = users_query.filter(
            User.id.in_(
                db.session.query(CohortMembership.user_id).filter(
                    CohortMembership.cohort_id == cohort_id
                )
            )
        )
    if lead_id is not None:
        lead = (
            User.query.join(Role)
            .join(RoleType)
            .filter(User.id == lead_id, User.is_active.is_(True), RoleType.code == "lead")
            .first()
        )
        if lead is None:
            abort(400, message="leadId must reference an active lead.")
        scoped_user_ids = [lead.id, *[user.id for user in lead.direct_reports if user.is_active]]
        users_query = users_query.filter(User.id.in_(scoped_user_ids))

    users = users_query.order_by(User.first_name, User.last_name).all()
    user_ids = [user.id for user in users]

    kairon_query = (
        db.session.query(KaironChartRecord.user_id, KaironChartRecord.status, func.count(KaironChartRecord.id))
        .join(KaironUploadBatch, KaironChartRecord.batch_id == KaironUploadBatch.id)
        .filter(
            KaironUploadBatch.superseded_at.is_(None),
            KaironChartRecord.status == "Completed",
            KaironChartRecord.completed_date >= from_date,
            KaironChartRecord.completed_date <= to_date,
            KaironChartRecord.user_id.isnot(None),
            KaironChartRecord.user_id.in_(user_ids),
        )
    )
    if program:
        kairon_query = kairon_query.filter(func.upper(KaironChartRecord.program) == program)
    kairon_rows = kairon_query.group_by(KaironChartRecord.user_id, KaironChartRecord.status).all()
    kairon_by_user = {}
    for user_id, status, count in kairon_rows:
        kairon_by_user.setdefault(user_id, {"active": 0, "on_hold": 0, "completed": 0})
        kairon_by_user[user_id][{"Active": "active", "On Hold": "on_hold", "Completed": "completed"}[status]] = count

    pvp_expression = ManualDailyRecord.pvp_count if program != "FOUNDATION" else 0
    foundation_expression = ManualDailyRecord.foundation_count if program != "PVP" else 0
    production_expression = pvp_expression + foundation_expression
    manual_rows = (
        db.session.query(
            ManualDailyRecord.user_id,
            func.sum(production_expression),
            func.sum(pvp_expression),
            func.sum(foundation_expression),
            func.sum(ManualDailyRecord.tech_issues_downtime_hours),
            func.sum(ManualDailyRecord.no_inventory_idle_time_hours),
            func.sum(ManualDailyRecord.leave_hours),
            func.sum(ManualDailyRecord.meeting_engagement_hours),
            func.sum(case((ManualDailyRecord.status == "pending", 1), else_=0)),
            func.count(ManualDailyRecord.id),
        )
        .filter(
            ManualDailyRecord.record_date >= from_date,
            ManualDailyRecord.record_date <= to_date,
            ManualDailyRecord.user_id.in_(user_ids),
        )
        .group_by(ManualDailyRecord.user_id)
        .all()
    )
    manual_by_user = {
        user_id: {
            "production_count": production_count,
            "pvp_count": pvp_count,
            "foundation_count": foundation_count,
            "tech_issues_downtime_hours": tech_hours,
            "no_inventory_idle_time_hours": idle_hours,
            "leave_hours": leave_hours,
            "meeting_engagement_hours": meeting_hours,
            "pending_count": pending_count,
            "record_count": record_count,
        }
        for (
            user_id,
            production_count,
            pvp_count,
            foundation_count,
            tech_hours,
            idle_hours,
            leave_hours,
            meeting_hours,
            pending_count,
            record_count,
        ) in manual_rows
    }
    efficiency_by_user = get_efficiency(
        user_ids,
        from_date,
        to_date,
        include_daily=include_daily,
        program=program,
    )

    return [
        {
            "user_id": user.id,
            "first_name": user.first_name,
            "last_name": user.last_name,
            "email": user.email,
            "kairon": kairon_by_user.get(user.id, {"active": 0, "on_hold": 0, "completed": 0}),
            "manual": manual_by_user.get(
                user.id,
                {
                    "production_count": 0,
                    "pvp_count": 0,
                    "foundation_count": 0,
                    "tech_issues_downtime_hours": 0,
                    "no_inventory_idle_time_hours": 0,
                    "leave_hours": 0,
                    "meeting_engagement_hours": 0,
                    "pending_count": 0,
                    "record_count": 0,
                },
            ),
            "efficiency": efficiency_by_user[user.id],
        }
        for user in users
    ]
