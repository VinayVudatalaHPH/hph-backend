"""add role feature permissions

Revision ID: 7c2d96ef301a
Revises: 1b4d70ac2351
"""

from alembic import op
import sqlalchemy as sa


revision = "7c2d96ef301a"
down_revision = "1b4d70ac2351"
branch_labels = None
depends_on = None


def upgrade():
    # Existing feature grants behaved as full access. Preserve that behavior
    # while allowing every later assignment to choose read and write explicitly.
    op.add_column(
        "role_features",
        sa.Column("can_read", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column(
        "role_features",
        sa.Column("can_write", sa.Boolean(), nullable=False, server_default=sa.true()),
    )


def downgrade():
    op.drop_column("role_features", "can_write")
    op.drop_column("role_features", "can_read")
