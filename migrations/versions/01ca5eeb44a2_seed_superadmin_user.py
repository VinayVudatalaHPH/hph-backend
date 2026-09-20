"""seed superadmin user

Revision ID: 01ca5eeb44a2
Revises: 1c52d29539e7
Create Date: 2026-09-16 20:03:29.016554

"""
from alembic import op
import sqlalchemy as sa
from argon2 import PasswordHasher


# revision identifiers, used by Alembic.
revision = '01ca5eeb44a2'
down_revision = '1c52d29539e7'
branch_labels = None
depends_on = None

roles_table = sa.table(
    "roles",
    sa.column("id", sa.Integer),
    sa.column("title", sa.String),
)

users_table = sa.table(
    "users",
    sa.column("email", sa.String),
    sa.column("first_name", sa.String),
    sa.column("last_name", sa.String),
    sa.column("emp_id", sa.String),
    sa.column("role_id", sa.Integer),
    sa.column("project_id", sa.Integer),
    sa.column("password_hash", sa.String),
    sa.column("first_login", sa.Boolean),
    sa.column("is_active", sa.Boolean),
)

SEED_EMAIL = "superadmin"


def upgrade():
    connection = op.get_bind()

    role_id = connection.execute(
        sa.select(roles_table.c.id).where(roles_table.c.title == "Super Admin")
    ).scalar_one()

    op.bulk_insert(
        users_table,
        [
            {
                "email": SEED_EMAIL,
                "first_name": "Super",
                "last_name": "Admin",
                "emp_id": "SUPERADMIN",
                "role_id": role_id,
                "project_id": None,
                "password_hash": PasswordHasher().hash("superadmin"),
                "first_login": False,
                "is_active": True,
            }
        ],
    )


def downgrade():
    connection = op.get_bind()
    connection.execute(users_table.delete().where(users_table.c.email == SEED_EMAIL))
