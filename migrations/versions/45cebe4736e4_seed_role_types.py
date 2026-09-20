"""seed role types

Revision ID: 45cebe4736e4
Revises: 51e4fdb8f620
Create Date: 2026-09-16 19:12:59.051366

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '45cebe4736e4'
down_revision = '51e4fdb8f620'
branch_labels = None
depends_on = None

role_types_table = sa.table(
    "role_types",
    sa.column("code", sa.String),
    sa.column("label", sa.String),
    sa.column("hierarchy_rank", sa.Integer),
    sa.column("session_timeout_minutes", sa.Integer),
)

SEED_ROLE_TYPES = [
    {"code": "super_admin", "label": "Super Admin", "hierarchy_rank": 0, "session_timeout_minutes": 30},
    {"code": "admin", "label": "Admin", "hierarchy_rank": 1, "session_timeout_minutes": 30},
    {"code": "manager", "label": "Manager", "hierarchy_rank": 2, "session_timeout_minutes": 30},
    {"code": "lead", "label": "Lead", "hierarchy_rank": 3, "session_timeout_minutes": 30},
    {"code": "employee", "label": "Employee", "hierarchy_rank": 4, "session_timeout_minutes": 30},
]


def upgrade():
    op.bulk_insert(role_types_table, SEED_ROLE_TYPES)


def downgrade():
    codes = [row["code"] for row in SEED_ROLE_TYPES]
    op.execute(role_types_table.delete().where(role_types_table.c.code.in_(codes)))
