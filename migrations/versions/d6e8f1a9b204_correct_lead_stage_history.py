"""correct historical steady-state dates for coding leads

Revision ID: d6e8f1a9b204
Revises: c5a7e2f8d441
"""

from alembic import op


revision = "d6e8f1a9b204"
down_revision = "c5a7e2f8d441"
branch_labels = None
depends_on = None


def upgrade():
    # Daily Refresh contains Kairon activity for these tenured leads from
    # April. Preserve any earlier user correction by moving only dates that
    # are currently later than the source-backed first activity date.
    op.execute(
        """
        UPDATE user_stage_periods AS period
        SET start_date = correction.start_date
        FROM users AS app_user
        JOIN (
            VALUES
                ('navyasri.dupati@humanpoweredhealth.com', DATE '2026-04-20'),
                ('zohra.syed@humanpoweredhealth.com', DATE '2026-04-21'),
                ('suja.nair@humanpoweredhealth.com', DATE '2026-04-21')
        ) AS correction(email, start_date)
          ON lower(app_user.email) = correction.email
        WHERE period.user_id = app_user.id
          AND period.stage_code = 'Steady State'
          AND period.start_date > correction.start_date
        """
    )


def downgrade():
    # Stage history may be edited after deployment. Do not overwrite those
    # later operational corrections during a schema downgrade.
    pass
