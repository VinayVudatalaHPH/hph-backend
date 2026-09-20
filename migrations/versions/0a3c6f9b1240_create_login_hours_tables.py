"""create login hours upload and record tables

Revision ID: 0a3c6f9b1240
Revises: f9b2d5e8a013
Create Date: 2026-09-19 18:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "0a3c6f9b1240"
down_revision = "f9b2d5e8a013"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "login_hours_upload_batches",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("source_format", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("matched_count", sa.Integer(), nullable=False),
        sa.Column("unmatched_count", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "login_hour_records",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("attendance_date", sa.Date(), nullable=False),
        sa.Column("employee_name_raw", sa.String(length=255), nullable=False),
        sa.Column("personnel_id", sa.String(length=64), nullable=True),
        sa.Column("department", sa.String(length=128), nullable=True),
        sa.Column("first_in", sa.Time(), nullable=True),
        sa.Column("last_out", sa.Time(), nullable=True),
        sa.Column("total_inside_minutes", sa.Integer(), nullable=False),
        sa.Column("total_outside_minutes", sa.Integer(), nullable=False),
        sa.Column("total_span_minutes", sa.Integer(), nullable=False),
        sa.Column("entries", sa.Integer(), nullable=False),
        sa.Column("exits", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=True),
        sa.Column("anomalies", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["login_hours_upload_batches.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "attendance_date", name="uq_login_hour_records_user_date"),
    )
    op.create_index("ix_login_hour_records_date", "login_hour_records", ["attendance_date"])


def downgrade():
    op.drop_index("ix_login_hour_records_date", table_name="login_hour_records")
    op.drop_table("login_hour_records")
    op.drop_table("login_hours_upload_batches")
