"""seed current stage target rules

Revision ID: 68747ecf172a
Revises: 43fee5898f9d
Create Date: 2026-09-18 11:24:27.205023

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '68747ecf172a'
down_revision = '43fee5898f9d'
branch_labels = None
depends_on = None

stage_target_rules_table = sa.table(
    "stage_target_rules",
    sa.column("stage_code", sa.String),
    sa.column("effective_from", sa.Date),
    sa.column("effective_to", sa.Date),
    sa.column("daily_target", sa.Integer),
    sa.column("created_by_id", sa.Integer),
)

users_table = sa.table(
    "users",
    sa.column("id", sa.Integer),
    sa.column("email", sa.String),
)

# The current 7/14/20/30/30 regime, seeded as one open-ended rule per stage.
# NOT seeding the prior 10/20/30/30 regime here - the actual date the org
# switched hasn't been supplied (see the dev spec's Target Resolution Logic
# and Migration Notes), so a historical row can't be dated accurately.
# EFFECTIVE_FROM is a placeholder far enough in the past to cover any
# existing coder's history until the real switchover date is known.
EFFECTIVE_FROM = "1900-01-01"

SEED_TARGETS = {
    "Training": None,  # Training has no chart-count target in either regime
    "M1": 7,
    "M2": 14,
    "M3": 20,
    "M4": 30,
    "Steady State": 30,
}


def upgrade():
    connection = op.get_bind()
    superadmin_id = connection.execute(
        sa.select(users_table.c.id).where(users_table.c.email == "superadmin")
    ).scalar_one()

    op.bulk_insert(
        stage_target_rules_table,
        [
            {
                "stage_code": stage_code,
                "effective_from": EFFECTIVE_FROM,
                "effective_to": None,
                "daily_target": daily_target,
                "created_by_id": superadmin_id,
            }
            for stage_code, daily_target in SEED_TARGETS.items()
            if daily_target is not None
        ],
    )


def downgrade():
    stage_codes = [code for code, target in SEED_TARGETS.items() if target is not None]
    op.execute(
        stage_target_rules_table.delete().where(stage_target_rules_table.c.stage_code.in_(stage_codes))
    )
