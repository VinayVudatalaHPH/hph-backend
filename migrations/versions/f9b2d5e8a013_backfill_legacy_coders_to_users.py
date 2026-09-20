"""backfill legacy cohort members and stage periods to users

Revision ID: f9b2d5e8a013
Revises: e8a1c4d7f902
Create Date: 2026-09-19 16:30:00.000000

"""
from alembic import op


revision = "f9b2d5e8a013"
down_revision = "e8a1c4d7f902"
branch_labels = None
depends_on = None


_MATCHED_CODERS = """
    SELECT
        coder.id AS coder_id,
        coder.cohort_id,
        coder.join_date,
        app_user.id AS user_id
    FROM coders AS coder
    JOIN users AS app_user
      ON regexp_replace(lower(coder.full_name), '[^a-z0-9]', '', 'g') =
         regexp_replace(lower(concat_ws(' ', app_user.first_name, app_user.last_name)), '[^a-z0-9]', '', 'g')
      OR (
          coder.full_name = 'Nedhanoori Yamuna Venkata Lakshmi'
          AND lower(app_user.email) = 'yamuna.nedhanoori@humanpoweredhealth.com'
      )
    JOIN roles AS role ON role.id = app_user.role_id
    JOIN role_types AS role_type ON role_type.id = role.role_type_id
    JOIN projects AS project ON project.id = app_user.project_id
    WHERE app_user.is_active = true
      AND project.name = 'CODING'
      AND role_type.code IN ('lead', 'employee')
"""


def upgrade():
    # Imported cohorts predate the user-backed Team UI. Link their legacy
    # coder identities to the authoritative CODING users without changing
    # the imported cohort assignments or stage dates.
    op.execute(
        f"""
        WITH matched AS ({_MATCHED_CODERS}),
        migration_actor AS (
            SELECT app_user.id
            FROM users AS app_user
            JOIN roles AS role ON role.id = app_user.role_id
            JOIN role_types AS role_type ON role_type.id = role.role_type_id
            WHERE role_type.code = 'super_admin'
            ORDER BY app_user.id
            LIMIT 1
        )
        INSERT INTO cohort_memberships
            (cohort_id, user_id, joined_on, assigned_by_id, assigned_at)
        SELECT matched.cohort_id, matched.user_id, matched.join_date,
               migration_actor.id, now()
        FROM matched
        CROSS JOIN migration_actor
        WHERE matched.cohort_id IS NOT NULL
          AND NOT EXISTS (
              SELECT 1 FROM cohort_memberships AS membership
              WHERE membership.user_id = matched.user_id
          )
        """
    )

    op.execute(
        f"""
        WITH matched AS ({_MATCHED_CODERS})
        INSERT INTO user_stage_periods
            (user_id, stage_code, start_date, end_date, source,
             shifted_by_exception_days)
        SELECT matched.user_id, period.stage_code, period.start_date,
               period.end_date, period.source,
               period.shifted_by_exception_days
        FROM matched
        JOIN coder_stage_periods AS period ON period.coder_id = matched.coder_id
        WHERE NOT EXISTS (
            SELECT 1 FROM user_stage_periods AS user_period
            WHERE user_period.user_id = matched.user_id
              AND user_period.stage_code = period.stage_code
        )
        """
    )

    # Only the latest cohort remains open for enrollment.
    op.execute(
        """
        WITH cohort_windows AS (
            SELECT id,
                   lead(window_start) OVER (ORDER BY sequence_no) AS next_start
            FROM cohorts
        )
        UPDATE cohorts AS cohort
        SET window_end = cohort_windows.next_start - 1
        FROM cohort_windows
        WHERE cohort.id = cohort_windows.id
          AND cohort.window_end IS NULL
          AND cohort_windows.next_start IS NOT NULL
        """
    )


def downgrade():
    # This migration only copies legacy operational data. Removing those
    # user links automatically is destructive and could erase memberships
    # created after deployment, so downgrade intentionally preserves them.
    pass
