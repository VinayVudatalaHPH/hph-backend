"""Manual daily production/attendance records: one row per user per
calendar day, entered by that user themselves (never uploaded in bulk,
never entered on someone else's behalf - see the module's design doc).

Unique per (user_id, record_date); the self-entry endpoint upserts on that
pair rather than ever creating a second row for the same person's same
day - see services.upsert_own_record().
"""
from app.extensions import db

VALID_STATUSES = ("pending", "approved", "rejected")

# Each of the four hour fields is independently capped at 10 - chosen to
# comfortably cover a long working day while still catching a
# minutes/hours mix-up (e.g. "40" for a single day). They are not required
# to sum to any particular total.
MAX_HOURS_PER_FIELD = 10


def _sql_in_list(values):
    return ", ".join(f"'{v}'" for v in values)


class ManualDailyRecord(db.Model):
    __tablename__ = "manual_daily_records"
    __table_args__ = (
        db.UniqueConstraint("user_id", "record_date", name="uq_manual_daily_records_user_date"),
        db.CheckConstraint("production_count >= 0", name="ck_manual_daily_records_production_count"),
        db.CheckConstraint("pvp_count >= 0", name="ck_manual_daily_records_pvp_count"),
        db.CheckConstraint("foundation_count >= 0", name="ck_manual_daily_records_foundation_count"),
        db.CheckConstraint(
            f"tech_issues_downtime_hours >= 0 AND tech_issues_downtime_hours <= {MAX_HOURS_PER_FIELD}",
            name="ck_manual_daily_records_tech_issues_downtime_hours",
        ),
        db.CheckConstraint(
            f"no_inventory_idle_time_hours >= 0 AND no_inventory_idle_time_hours <= {MAX_HOURS_PER_FIELD}",
            name="ck_manual_daily_records_no_inventory_idle_time_hours",
        ),
        db.CheckConstraint(
            f"leave_hours >= 0 AND leave_hours <= {MAX_HOURS_PER_FIELD}",
            name="ck_manual_daily_records_leave_hours",
        ),
        db.CheckConstraint(
            f"meeting_engagement_hours >= 0 AND meeting_engagement_hours <= {MAX_HOURS_PER_FIELD}",
            name="ck_manual_daily_records_meeting_engagement_hours",
        ),
        db.CheckConstraint(f"status IN ({_sql_in_list(VALID_STATUSES)})", name="ck_manual_daily_records_status"),
    )

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    record_date = db.Column(db.Date, nullable=False)

    production_count = db.Column(db.Integer, nullable=False)
    pvp_count = db.Column(db.Integer, nullable=False, default=0)
    foundation_count = db.Column(db.Integer, nullable=False, default=0)
    tech_issues_downtime_hours = db.Column(db.Numeric(4, 2), nullable=False, default=0)
    no_inventory_idle_time_hours = db.Column(db.Numeric(4, 2), nullable=False, default=0)
    leave_hours = db.Column(db.Numeric(4, 2), nullable=False, default=0)
    meeting_engagement_hours = db.Column(db.Numeric(4, 2), nullable=False, default=0)

    status = db.Column(db.String(16), nullable=False, default="pending")
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    reviewed_at = db.Column(db.DateTime(timezone=True), nullable=True)
    # Only ever meaningful for a rejection - so the coder knows what to fix.
    rejection_reason = db.Column(db.Text, nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime(timezone=True), server_default=db.func.now(), onupdate=db.func.now(), nullable=False
    )

    user = db.relationship("User", foreign_keys=[user_id], backref="manual_daily_records")
    reviewed_by = db.relationship("User", foreign_keys=[reviewed_by_id])

    def __repr__(self):
        return f"<ManualDailyRecord user_id={self.user_id} date={self.record_date} status={self.status}>"
