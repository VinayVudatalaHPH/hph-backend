"""add user cohort memberships, stage periods, and target audit fields

Revision ID: e8a1c4d7f902
Revises: d4f6a7b8c901
Create Date: 2026-09-19 15:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "e8a1c4d7f902"
down_revision = "d4f6a7b8c901"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("stage_target_rules", sa.Column("reason", sa.Text(), nullable=True))
    op.add_column(
        "stage_target_rules",
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )

    op.create_table(
        "cohort_memberships",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("cohort_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("joined_on", sa.Date(), nullable=False),
        sa.Column("assigned_by_id", sa.Integer(), nullable=False),
        sa.Column("assigned_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["assigned_by_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["cohort_id"], ["cohorts.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_cohort_memberships_user"),
    )

    op.create_table(
        "user_stage_periods",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("stage_code", sa.String(length=32), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column("shifted_by_exception_days", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "source IN ('observed_first_activity', 'calendar_offset', 'manual_override')",
            name="ck_user_stage_periods_source",
        ),
        sa.ForeignKeyConstraint(["stage_code"], ["stages.code"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "stage_code", name="uq_user_stage_periods_user_stage"),
    )


def downgrade():
    op.drop_table("user_stage_periods")
    op.drop_table("cohort_memberships")
    op.drop_column("stage_target_rules", "created_at")
    op.drop_column("stage_target_rules", "reason")
