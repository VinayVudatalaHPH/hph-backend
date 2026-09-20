"""add user reporting lines

Revision ID: d4f6a7b8c901
Revises: 565bd59f4f7b
Create Date: 2026-09-19 11:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "d4f6a7b8c901"
down_revision = "565bd59f4f7b"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("reports_to_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_users_reports_to_id_users",
        "users",
        "users",
        ["reports_to_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_users_reports_to_id", "users", ["reports_to_id"])

    # Preserve a useful hierarchy for simple existing projects. Ambiguous
    # projects (multiple managers or multiple leads) are intentionally left
    # unassigned for an administrator to resolve in the Users screen.
    op.execute(
        """
        UPDATE users AS team_lead
        SET reports_to_id = sole_manager.manager_id
        FROM (
            SELECT manager.project_id, MIN(manager.id) AS manager_id
            FROM users AS manager
            JOIN roles AS manager_role ON manager_role.id = manager.role_id
            JOIN role_types AS manager_type ON manager_type.id = manager_role.role_type_id
            WHERE manager_type.code = 'manager' AND manager.is_active = TRUE
            GROUP BY manager.project_id
            HAVING COUNT(*) = 1
        ) AS sole_manager
        WHERE team_lead.project_id = sole_manager.project_id
          AND team_lead.reports_to_id IS NULL
          AND EXISTS (
              SELECT 1
              FROM roles AS lead_role
              JOIN role_types AS lead_type ON lead_type.id = lead_role.role_type_id
              WHERE lead_role.id = team_lead.role_id AND lead_type.code = 'lead'
          )
        """
    )
    op.execute(
        """
        UPDATE users AS employee
        SET reports_to_id = sole_lead.lead_id
        FROM (
            SELECT team_lead.project_id, MIN(team_lead.id) AS lead_id
            FROM users AS team_lead
            JOIN roles AS lead_role ON lead_role.id = team_lead.role_id
            JOIN role_types AS lead_type ON lead_type.id = lead_role.role_type_id
            WHERE lead_type.code = 'lead' AND team_lead.is_active = TRUE
            GROUP BY team_lead.project_id
            HAVING COUNT(*) = 1
        ) AS sole_lead
        WHERE employee.project_id = sole_lead.project_id
          AND employee.reports_to_id IS NULL
          AND EXISTS (
              SELECT 1
              FROM roles AS employee_role
              JOIN role_types AS employee_type ON employee_type.id = employee_role.role_type_id
              WHERE employee_role.id = employee.role_id AND employee_type.code = 'employee'
          )
        """
    )


def downgrade():
    op.drop_index("ix_users_reports_to_id", table_name="users")
    op.drop_constraint("fk_users_reports_to_id_users", "users", type_="foreignkey")
    op.drop_column("users", "reports_to_id")
