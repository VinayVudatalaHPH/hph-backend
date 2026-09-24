"""create office holidays and seed the 2026 calendar

Revision ID: b4c7d9e2f105
Revises: a2d7e4f9c103
"""
from alembic import op
import sqlalchemy as sa
from datetime import date


revision = "b4c7d9e2f105"
down_revision = "a2d7e4f9c103"
branch_labels = None
depends_on = None


HOLIDAYS_2026 = (
    ("2026-01-01", "New Year's Day", "public"),
    ("2026-01-14", "Makar Sankranti / Pongal", "public"),
    ("2026-01-26", "Republic Day", "national"),
    ("2026-05-01", "May Day", "public"),
    ("2026-06-02", "Telangana Formation Day", "public"),
    ("2026-09-14", "Ganesh Chaturthi / Vinayaka Chaturthi", "public"),
    ("2026-10-02", "Mahatma Gandhi Jayanti", "national"),
    ("2026-10-21", "Dussera", "public"),
    ("2026-11-09", "Deepawali / Diwali", "public"),
    ("2026-12-25", "Christmas", "public"),
)


def upgrade():
    table = op.create_table(
        "office_holidays",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("holiday_date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=32), server_default="public", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("holiday_date", name="uq_office_holidays_date"),
    )
    op.create_index("ix_office_holidays_holiday_date", "office_holidays", ["holiday_date"])
    op.bulk_insert(
        table,
        [
            {"holiday_date": date.fromisoformat(date_value), "name": name, "category": category}
            for date_value, name, category in HOLIDAYS_2026
        ],
    )

    connection = op.get_bind()
    role_exists = connection.execute(
        sa.text("SELECT 1 FROM pg_roles WHERE rolname = 'hph_app'")
    ).scalar()
    if role_exists:
        op.execute("GRANT SELECT, INSERT, UPDATE, DELETE ON office_holidays TO hph_app")
        op.execute("GRANT USAGE, SELECT ON SEQUENCE office_holidays_id_seq TO hph_app")


def downgrade():
    op.drop_index("ix_office_holidays_holiday_date", table_name="office_holidays")
    op.drop_table("office_holidays")
