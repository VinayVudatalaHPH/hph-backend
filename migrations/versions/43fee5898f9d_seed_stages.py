"""seed stages

Revision ID: 43fee5898f9d
Revises: 2bafdaae6e3b
Create Date: 2026-09-18 11:24:26.573007

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '43fee5898f9d'
down_revision = '2bafdaae6e3b'
branch_labels = None
depends_on = None

stages_table = sa.table(
    "stages",
    sa.column("code", sa.String),
    sa.column("sort_order", sa.Integer),
    sa.column("duration_days", sa.Integer),
)

# Fixed path order and durations, per the dev spec's "durations are fixed"
# decision - Training ~2 weeks, M1-M4 ~30 days each, Steady State open-ended.
SEED_STAGES = [
    {"code": "Training", "sort_order": 1, "duration_days": 14},
    {"code": "M1", "sort_order": 2, "duration_days": 30},
    {"code": "M2", "sort_order": 3, "duration_days": 30},
    {"code": "M3", "sort_order": 4, "duration_days": 30},
    {"code": "M4", "sort_order": 5, "duration_days": 30},
    {"code": "Steady State", "sort_order": 6, "duration_days": None},
]


def upgrade():
    op.bulk_insert(stages_table, SEED_STAGES)


def downgrade():
    codes = [row["code"] for row in SEED_STAGES]
    op.execute(stages_table.delete().where(stages_table.c.code.in_(codes)))
