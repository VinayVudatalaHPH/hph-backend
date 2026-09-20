from flask import g
from flask.views import MethodView
from flask_smorest import abort

from app.auth import require_feature, require_role, require_role_types
from app.extensions import db
from app.manual_daily_records import bp
from app.manual_daily_records.models import ManualDailyRecord
from app.manual_daily_records.schemas import (
    ManualDailyRecordEnvelopeSchema,
    ManualDailyRecordListEnvelopeSchema,
    ManualDailyRecordQuerySchema,
    ManualDailyRecordUpsertSchema,
    RejectManualDailyRecordSchema,
)
from app.manual_daily_records.services import approve_record, reject_record, upsert_own_record

# Manual records belong to Reports. Manager/Lead/Employee roles with Reports
# write may submit their own record; approving/rejecting remains Manager-only.
REPORTS_FEATURE = "reports"


@bp.route("/manual-daily-records")
class ManualDailyRecords(MethodView):
    @require_feature(REPORTS_FEATURE)
    @bp.arguments(ManualDailyRecordQuerySchema, location="query")
    @bp.response(200, ManualDailyRecordListEnvelopeSchema)
    def get(self, args):
        # Doubles as the manager's review queue (?status=pending) and as
        # general reporting (§8) - same endpoint, different filter combo.
        query = ManualDailyRecord.query
        if args.get("from_date"):
            query = query.filter(ManualDailyRecord.record_date >= args["from_date"])
        if args.get("to_date"):
            query = query.filter(ManualDailyRecord.record_date <= args["to_date"])
        if args.get("user_id"):
            query = query.filter(ManualDailyRecord.user_id == args["user_id"])
        if args.get("user_ids"):
            query = query.filter(ManualDailyRecord.user_id.in_(args["user_ids"]))
        if args.get("exclude_user_ids"):
            query = query.filter(ManualDailyRecord.user_id.notin_(args["exclude_user_ids"]))
        if args.get("status"):
            query = query.filter(ManualDailyRecord.status == args["status"])
        records = query.order_by(ManualDailyRecord.record_date.desc()).all()
        return {"status": 200, "message": "Manual daily records retrieved successfully.", "data": records}

    @require_feature(REPORTS_FEATURE, access="write")
    @require_role_types("manager", "lead", "employee")
    @bp.arguments(ManualDailyRecordUpsertSchema)
    @bp.response(200, ManualDailyRecordEnvelopeSchema)
    def post(self, data):
        # Always the caller's own record - there is no manager-entered or
        # on-behalf-of path (§4), so no user id is ever accepted here.
        record = upsert_own_record(g.user.id, data)
        return {"status": 200, "message": "Manual daily record saved successfully.", "data": record}


@bp.route("/manual-daily-records/<int:record_id>/approve")
class ApproveManualDailyRecord(MethodView):
    @require_feature(REPORTS_FEATURE, access="write")
    @require_role("manager")
    @bp.response(200, ManualDailyRecordEnvelopeSchema)
    def post(self, record_id):
        record = ManualDailyRecord.query.get_or_404(record_id)
        if record.status != "pending":
            abort(409, message="This record isn't pending review.")

        approve_record(record, g.user.id)
        db.session.commit()
        return {"status": 200, "message": "Manual daily record approved successfully.", "data": record}


@bp.route("/manual-daily-records/<int:record_id>/reject")
class RejectManualDailyRecord(MethodView):
    @require_feature(REPORTS_FEATURE, access="write")
    @require_role("manager")
    @bp.arguments(RejectManualDailyRecordSchema)
    @bp.response(200, ManualDailyRecordEnvelopeSchema)
    def post(self, data, record_id):
        record = ManualDailyRecord.query.get_or_404(record_id)
        if record.status != "pending":
            abort(409, message="This record isn't pending review.")

        reject_record(record, g.user.id, data.get("reason"))
        db.session.commit()
        return {"status": 200, "message": "Manual daily record rejected successfully.", "data": record}
