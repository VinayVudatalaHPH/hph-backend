"""Kairon chart-review records: the per-chart coding/QA ledger pulled from
Kairon exports (Program, Level, Status, Coding Analyst, Actions, Last
Action, Created, Completed, TAT, Age, Practice) - modeled directly on a
real `coding_ops_tasks` export.

Patient name and MBI are deliberately never modelled here. Kairon's real
export carries patient PHI in those two columns; this table exists to
track coder/QA workflow, not patient identity, so those columns simply
have no field to hold them - the upload schema (kairon/schemas.py) also
actively rejects a payload that mentions them, rather than silently
dropping the value if a client's export tool still includes it.

Because a chart row therefore carries no unique patient/MBI identifier,
there is no reliable way to de-duplicate an individual row against a
prior upload. Each upload is instead one `KaironUploadBatch` snapshot "as
of" a manager-selected date; re-uploading for the same as_of_date
supersedes the prior batch's rows (kept, not deleted, for audit) rather
than merging row-by-row - see services.import_batch().
"""
from app.extensions import db

VALID_KAIRON_LEVELS = ("1LR", "2LR", "3LR")
# Observed in the real export: Active, On Hold, Completed. Kept as a plain
# CheckConstraint tuple (matching cohorts/models.py's VALID_PERIOD_SOURCES
# style) rather than a lookup table, since - unlike Stage - there's no
# other per-status metadata to hang off it; extending the set is a
# migration that widens this constraint.
VALID_KAIRON_STATUSES = ("Active", "On Hold", "Completed")


def _sql_in_list(values):
    return ", ".join(f"'{v}'" for v in values)


class KaironUploadBatch(db.Model):
    """One bulk-upload event. `as_of_date` is the reporting date the
    manager selects in the UI after uploading - distinct from any row's
    own Created/Completed dates, and the key a same-date re-upload
    supersedes on (see the module docstring).
    """

    __tablename__ = "kairon_upload_batches"

    id = db.Column(db.Integer, primary_key=True)
    as_of_date = db.Column(db.Date, nullable=False)
    source_filename = db.Column(db.String(255), nullable=True)
    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    uploaded_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)
    row_count = db.Column(db.Integer, nullable=False, default=0)
    matched_count = db.Column(db.Integer, nullable=False, default=0)
    unmatched_count = db.Column(db.Integer, nullable=False, default=0)
    # Set when a later batch for the same as_of_date replaces this one.
    # Rows stay in place for audit rather than being deleted.
    superseded_at = db.Column(db.DateTime(timezone=True), nullable=True)
    superseded_by_id = db.Column(db.Integer, db.ForeignKey("kairon_upload_batches.id"), nullable=True)

    uploaded_by = db.relationship("User")
    superseded_by = db.relationship("KaironUploadBatch", remote_side=[id])

    def __repr__(self):
        return f"<KaironUploadBatch id={self.id} as_of={self.as_of_date}>"


class KaironChartRecord(db.Model):
    __tablename__ = "kairon_chart_records"
    __table_args__ = (
        db.CheckConstraint(
            f"level IN ({_sql_in_list(VALID_KAIRON_LEVELS)})", name="ck_kairon_chart_records_level"
        ),
        db.CheckConstraint(
            f"status IN ({_sql_in_list(VALID_KAIRON_STATUSES)})", name="ck_kairon_chart_records_status"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    batch_id = db.Column(db.Integer, db.ForeignKey("kairon_upload_batches.id"), nullable=False)

    program = db.Column(db.String(64), nullable=False)
    level = db.Column(db.String(16), nullable=False)
    status = db.Column(db.String(32), nullable=False)

    # Required: a row whose Coding Analyst name doesn't resolve to a User
    # is never saved (see services.import_batch), so there is no "pending
    # resolution" state to represent here. The raw string is still kept
    # alongside it for audit, matching Phase 1.5's personnel_id/employee_name
    # handling. Resolves to the platform's login identity (User), not
    # cohorts' separate Coder entity - see services.resolve_user() and the
    # module docstring.
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    coding_analyst_raw = db.Column(db.String(255), nullable=False)

    actions = db.Column(db.Integer, nullable=False, default=0)
    last_action = db.Column(db.Text, nullable=True)
    created_date = db.Column(db.Date, nullable=False)
    completed_date = db.Column(db.Date, nullable=True)
    tat_days = db.Column(db.Integer, nullable=True)
    age_days = db.Column(db.Integer, nullable=True)
    practice = db.Column(db.String(255), nullable=True)

    created_at = db.Column(db.DateTime(timezone=True), server_default=db.func.now(), nullable=False)

    batch = db.relationship("KaironUploadBatch", backref="records")
    user = db.relationship("User", backref="kairon_chart_records")

    def __repr__(self):
        return f"<KaironChartRecord id={self.id} level={self.level} status={self.status}>"


class KaironChartAnalystAction(db.Model):
    """A chart's per-touch analyst history - a genuine many-to-many
    between chart records and users (one chart can, over its life, be
    touched by several analysts across 1LR/2LR/3LR; one analyst touches
    many charts), kept as its own table per the requirement that Kairon
    records link into the user identity many-to-many.

    Today's export only ever gives one action per uploaded row (the
    row's own Actions/Last Action/Coding Analyst), so import_batch()
    records exactly that one action now - this table is ready to hold a
    full multi-analyst handoff chain the day Kairon's export includes one,
    without a schema change.
    """

    __tablename__ = "kairon_chart_analyst_actions"

    id = db.Column(db.Integer, primary_key=True)
    chart_record_id = db.Column(db.Integer, db.ForeignKey("kairon_chart_records.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    level = db.Column(db.String(16), nullable=False)
    action_text = db.Column(db.Text, nullable=True)
    action_date = db.Column(db.Date, nullable=True)
    sequence_no = db.Column(db.Integer, nullable=False, default=1)

    chart_record = db.relationship("KaironChartRecord", backref="analyst_actions")
    user = db.relationship("User")

    def __repr__(self):
        return f"<KaironChartAnalystAction chart_record_id={self.chart_record_id} user_id={self.user_id}>"
