"""add manual program counts

Revision ID: c5a7e2f8d441
Revises: b9e4d1a7c322
"""

from alembic import op
import sqlalchemy as sa


revision = "c5a7e2f8d441"
down_revision = "b9e4d1a7c322"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "manual_daily_records",
        sa.Column("pvp_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "manual_daily_records",
        sa.Column("foundation_count", sa.Integer(), nullable=False, server_default="0"),
    )
    # Existing production was not program-tagged. Per the product decision,
    # preserve every total as PVP and leave Foundation at zero.
    op.execute("UPDATE manual_daily_records SET pvp_count = production_count, foundation_count = 0")
    op.create_check_constraint(
        "ck_manual_daily_records_pvp_count",
        "manual_daily_records",
        "pvp_count >= 0",
    )
    op.create_check_constraint(
        "ck_manual_daily_records_foundation_count",
        "manual_daily_records",
        "foundation_count >= 0",
    )


def downgrade():
    op.drop_constraint(
        "ck_manual_daily_records_foundation_count",
        "manual_daily_records",
        type_="check",
    )
    op.drop_constraint(
        "ck_manual_daily_records_pvp_count",
        "manual_daily_records",
        type_="check",
    )
    op.drop_column("manual_daily_records", "foundation_count")
    op.drop_column("manual_daily_records", "pvp_count")

