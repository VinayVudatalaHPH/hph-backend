"""seed features

Revision ID: 6aa3f7dde73f
Revises: 1ff29f59361d
Create Date: 2026-09-16 19:46:53.787737

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '6aa3f7dde73f'
down_revision = '1ff29f59361d'
branch_labels = None
depends_on = None

features_table = sa.table(
    "features",
    sa.column("codename", sa.String),
    sa.column("title", sa.String),
    sa.column("description", sa.Text),
    sa.column("active", sa.Boolean),
)

SEED_FEATURES = [
    {"codename": "user_management", "title": "User Management", "description": "Create, view, and manage user accounts.", "active": True},
    {"codename": "role_management", "title": "Role Management", "description": "Create and manage role profiles and their assigned features.", "active": True},
    {"codename": "dashboard", "title": "Dashboard", "description": "Access to the dashboard views.", "active": True},
    {"codename": "login_hours_management", "title": "Login Hours Management", "description": "Upload and manage login hours data.", "active": True},
]


def upgrade():
    op.bulk_insert(features_table, SEED_FEATURES)


def downgrade():
    codenames = [row["codename"] for row in SEED_FEATURES]
    op.execute(features_table.delete().where(features_table.c.codename.in_(codenames)))
