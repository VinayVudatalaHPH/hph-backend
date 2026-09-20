"""Kairon chart-record ingestion: reference-template generation,
coding-analyst name resolution, and the batch-supersede import itself.

Patient name and MBI never reach this module. The upload schema
(kairon/schemas.py) has no field for either one and actively rejects a
payload that mentions them, so there is nothing here to scrub - this is
the third of three layers (the template below, the schema, this
docstring) that all agree those two columns simply do not exist in this
system.
"""
import csv
import io
import re
from datetime import datetime, timezone

from app.extensions import db
from app.kairon.models import KaironChartAnalystAction, KaironChartRecord, KaironUploadBatch
from app.users.models import User

# The exact columns (and order) the reference template offers, matching
# KaironChartRowSchema's whitelist one-for-one. Patient and MBI are
# deliberately absent - see the module docstring.
TEMPLATE_COLUMNS = (
    "Program",
    "Level",
    "Status",
    "Coding Analyst",
    "Actions",
    "Last Action",
    "Created",
    "Completed",
    "TAT",
    "Age",
    "Practice",
)

# Kairon's export always suffixes the analyst's name with their role,
# e.g. "Charishma Sonani - HPH Coding Analyst" - strip everything from the
# first " - " onward once here rather than in every caller.
_ANALYST_SUFFIX_RE = re.compile(r"\s*-\s*.*$")


def build_upload_template_csv():
    """The blank reference file a manager downloads before a bulk upload -
    header row only, in the one order the upload schema accepts."""
    buffer = io.StringIO()
    csv.writer(buffer).writerow(TEMPLATE_COLUMNS)
    return buffer.getvalue()


def normalize_analyst_name(raw_name):
    """'Charishma Sonani - HPH Coding Analyst' -> 'Charishma Sonani'."""
    return _ANALYST_SUFFIX_RE.sub("", raw_name or "").strip()


def resolve_user(raw_name):
    """Looks up `raw_name` against the platform's login identity (User),
    comparing its first/last name case- and whitespace-insensitively.
    Returns the User, or None if nothing matches - a row whose analyst
    doesn't resolve is never saved (see import_batch) rather than
    guessing or silently creating a new account. Create the User first,
    then re-upload the row.

    This resolves against User directly, not the cohorts feature's
    separate Coder entity - see the module docstring.
    """
    name = normalize_analyst_name(raw_name)
    if not name:
        return None

    full_name = db.func.lower(db.func.trim(User.first_name) + " " + db.func.trim(User.last_name))
    return User.query.filter(full_name == name.lower()).first()


def _supersede_existing_batches(as_of_date, new_batch_id):
    now = datetime.now(timezone.utc)
    stale_batches = KaironUploadBatch.query.filter(
        KaironUploadBatch.as_of_date == as_of_date,
        KaironUploadBatch.id != new_batch_id,
        KaironUploadBatch.superseded_at.is_(None),
    ).all()
    for stale in stale_batches:
        stale.superseded_at = now
        stale.superseded_by_id = new_batch_id


def import_batch(as_of_date, rows, uploaded_by_id, source_filename=None):
    """Creates one KaironUploadBatch and its KaironChartRecord (+
    KaironChartAnalystAction) rows from an already-validated row list
    (KaironUploadRequestSchema's `rows` output).

    A row whose Coding Analyst doesn't resolve to an existing User is
    never saved - user_id is a required field on both KaironChartRecord
    and KaironChartAnalystAction, so there is nothing to save it as.
    Such rows are skipped and their raw names are collected on the
    returned batch (as `unmatched_names`, alongside the persisted
    `unmatched_count`) so the caller can report them; fix the row by
    creating the User (or correcting the name) and re-uploading.

    There is no patient/MBI identifier to de-duplicate an individual row
    against a prior upload, so re-uploading for the same as_of_date does
    not try to merge row-by-row: it supersedes the prior batch(es) for
    that date (kept, not deleted, for audit - see
    _supersede_existing_batches) and this batch becomes the one active
    queries read (KaironChartRecord queries in routes.py always filter to
    batch.superseded_at IS NULL). Correcting a bad upload is therefore
    "upload the corrected file with the same as-of date", not a
    row-level edit screen - matching the rule that only a manager may
    change this data at all (enforced at the route layer via
    the Reports write and Manager-role guards, not here).
    """
    batch = KaironUploadBatch(
        as_of_date=as_of_date,
        source_filename=source_filename,
        uploaded_by_id=uploaded_by_id,
        row_count=len(rows),
    )
    db.session.add(batch)
    db.session.flush()  # assigns batch.id

    matched_count = 0
    unmatched_names = []
    completed_user_ids = set()
    for row in rows:
        user = resolve_user(row["coding_analyst"])
        if user is None:
            unmatched_names.append(row["coding_analyst"])
            continue

        record = KaironChartRecord(
            batch_id=batch.id,
            program=row["program"],
            level=row["level"],
            status=row["status"],
            user_id=user.id,
            coding_analyst_raw=row["coding_analyst"],
            actions=row.get("actions", 0),
            last_action=row.get("last_action"),
            created_date=row["created_date"],
            completed_date=row.get("completed_date"),
            tat_days=row.get("tat_days"),
            age_days=row.get("age_days"),
            practice=row.get("practice"),
        )
        db.session.add(record)
        db.session.flush()  # assigns record.id, needed below
        if row["status"] == "Completed" and row.get("completed_date") is not None:
            completed_user_ids.add(user.id)

        # Today's export gives one action per row; recorded as sequence 1
        # of what can later become a full multi-analyst chain (see
        # KaironChartAnalystAction's docstring) without a schema change.
        db.session.add(
            KaironChartAnalystAction(
                chart_record_id=record.id,
                user_id=user.id,
                level=row["level"],
                action_text=row.get("last_action"),
                action_date=row.get("completed_date") or row["created_date"],
                sequence_no=1,
            )
        )
        matched_count += 1

    batch.matched_count = matched_count
    batch.unmatched_count = len(unmatched_names)
    # Not a mapped column - transient, dump-only reporting for this
    # request's response (KaironUploadBatchSchema.unmatched_names) since
    # the skipped rows themselves are never persisted.
    batch.unmatched_names = unmatched_names
    _supersede_existing_batches(as_of_date, batch.id)
    db.session.commit()

    if completed_user_ids:
        from app.cohorts.models import CohortMembership
        from app.cohorts.services import compute_user_stage_periods

        memberships = CohortMembership.query.filter(CohortMembership.user_id.in_(completed_user_ids)).all()
        for membership in memberships:
            compute_user_stage_periods(membership)
        if memberships:
            db.session.commit()
    return batch
