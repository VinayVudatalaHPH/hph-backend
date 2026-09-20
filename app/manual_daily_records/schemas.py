from marshmallow import Schema, ValidationError, fields, validate, validates_schema

from app.manual_daily_records.models import MAX_HOURS_PER_FIELD, VALID_STATUSES
from app.responses import envelope_schema

def _hour_field(**kwargs):
    return fields.Decimal(places=2, validate=validate.Range(min=0, max=MAX_HOURS_PER_FIELD), **kwargs)


class ManualDailyRecordUpsertSchema(Schema):
    """POST /api/manual-daily-records body. There's no user field - the
    record is always saved against whoever is logged in (see
    services.upsert_own_record) - and no batch/as-of date, just the one
    day this entry is for.
    """

    record_date = fields.Date(required=True, data_key="date")
    pvp_count = fields.Integer(load_default=None, allow_none=True, validate=validate.Range(min=0), data_key="pvpCount")
    foundation_count = fields.Integer(
        load_default=None, allow_none=True, validate=validate.Range(min=0), data_key="foundationCount"
    )
    # Temporary compatibility for older clients. New clients submit the two
    # program counts; the server always derives the total.
    production_count = fields.Integer(
        load_default=None, allow_none=True, validate=validate.Range(min=0), data_key="productionCount"
    )
    tech_issues_downtime_hours = _hour_field(required=True, data_key="techIssuesDowntimeHours")
    no_inventory_idle_time_hours = _hour_field(required=True, data_key="noInventoryIdleTimeHours")
    leave_hours = _hour_field(required=True, data_key="leaveHours")
    meeting_engagement_hours = _hour_field(required=True, data_key="meetingEngagementHours")

    @validates_schema
    def derive_production_count(self, data, **kwargs):
        pvp_count = data.get("pvp_count")
        foundation_count = data.get("foundation_count")
        legacy_total = data.get("production_count")
        if pvp_count is None and foundation_count is None:
            if legacy_total is None:
                raise ValidationError(
                    "PVP count and Foundation count are required.",
                    field_name="pvpCount",
                )
            pvp_count, foundation_count = legacy_total, 0
        else:
            pvp_count = pvp_count or 0
            foundation_count = foundation_count or 0
        data["pvp_count"] = pvp_count
        data["foundation_count"] = foundation_count
        data["production_count"] = pvp_count + foundation_count


class ManualDailyRecordSchema(Schema):
    id = fields.Integer(dump_only=True)
    user_id = fields.Integer(dump_only=True, data_key="userId")
    record_date = fields.Date(dump_only=True, data_key="date")
    production_count = fields.Integer(dump_only=True, data_key="productionCount")
    pvp_count = fields.Integer(dump_only=True, data_key="pvpCount")
    foundation_count = fields.Integer(dump_only=True, data_key="foundationCount")
    tech_issues_downtime_hours = fields.Decimal(dump_only=True, as_string=True, data_key="techIssuesDowntimeHours")
    no_inventory_idle_time_hours = fields.Decimal(
        dump_only=True, as_string=True, data_key="noInventoryIdleTimeHours"
    )
    leave_hours = fields.Decimal(dump_only=True, as_string=True, data_key="leaveHours")
    meeting_engagement_hours = fields.Decimal(dump_only=True, as_string=True, data_key="meetingEngagementHours")
    status = fields.String(dump_only=True)
    reviewed_by_id = fields.Integer(dump_only=True, allow_none=True, data_key="reviewedById")
    reviewed_at = fields.DateTime(dump_only=True, allow_none=True, data_key="reviewedAt")
    rejection_reason = fields.String(dump_only=True, allow_none=True, data_key="rejectionReason")
    created_at = fields.DateTime(dump_only=True, data_key="createdAt")
    updated_at = fields.DateTime(dump_only=True, data_key="updatedAt")


class ManualDailyRecordQuerySchema(Schema):
    """Backs all four read patterns from §8: a date range, a single user, a
    named group (as an ad hoc user-id list - see the Kairon doc's identical
    fallback, since the Cohort<->User bridge doesn't exist yet), and
    "everyone except" a given set. A manager's review queue is just this
    same listing filtered to status=pending.
    """

    from_date = fields.Date(required=False, load_default=None, data_key="fromDate")
    to_date = fields.Date(required=False, load_default=None, data_key="toDate")
    user_id = fields.Integer(required=False, load_default=None, data_key="userId")
    user_ids = fields.List(fields.Integer(), required=False, load_default=None, data_key="userIds")
    exclude_user_ids = fields.List(fields.Integer(), required=False, load_default=None, data_key="excludeUserIds")
    lead_id = fields.Integer(required=False, load_default=None, data_key="leadId")
    status = fields.String(required=False, load_default=None, validate=validate.OneOf(VALID_STATUSES))


class RejectManualDailyRecordSchema(Schema):
    reason = fields.String(required=False, load_default=None, allow_none=True)


ManualDailyRecordEnvelopeSchema = envelope_schema(
    "ManualDailyRecordEnvelopeSchema", fields.Nested(ManualDailyRecordSchema)
)
ManualDailyRecordListEnvelopeSchema = envelope_schema(
    "ManualDailyRecordListEnvelopeSchema", fields.List(fields.Nested(ManualDailyRecordSchema))
)
