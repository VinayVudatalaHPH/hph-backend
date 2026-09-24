"""add user last working day

Revision ID: 4e6f91a2c8d0
Revises: d6e8f1a9b204
Create Date: 2026-09-24 12:25:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "4e6f91a2c8d0"
down_revision = "d6e8f1a9b204"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("last_working_day", sa.Date(), nullable=True))


def downgrade():
    op.drop_column("users", "last_working_day")
