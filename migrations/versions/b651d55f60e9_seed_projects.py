"""seed projects

Revision ID: b651d55f60e9
Revises: 62812d29913b
Create Date: 2026-09-16 19:57:22.105716

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b651d55f60e9'
down_revision = '62812d29913b'
branch_labels = None
depends_on = None

projects_table = sa.table(
    "projects",
    sa.column("name", sa.String),
)

SEED_PROJECTS = [
    {"name": "RCM"},
    {"name": "CODING"},
]


def upgrade():
    op.bulk_insert(projects_table, SEED_PROJECTS)


def downgrade():
    names = [row["name"] for row in SEED_PROJECTS]
    op.execute(projects_table.delete().where(projects_table.c.name.in_(names)))
