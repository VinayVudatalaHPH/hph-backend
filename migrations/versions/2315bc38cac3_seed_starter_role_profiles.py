"""seed starter role profiles

Revision ID: 2315bc38cac3
Revises: 6aa3f7dde73f
Create Date: 2026-09-16 19:53:52.360163

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2315bc38cac3'
down_revision = '6aa3f7dde73f'
branch_labels = None
depends_on = None

role_types_table = sa.table(
    "role_types",
    sa.column("id", sa.Integer),
    sa.column("code", sa.String),
)

features_table = sa.table(
    "features",
    sa.column("id", sa.Integer),
    sa.column("codename", sa.String),
)

roles_table = sa.table(
    "roles",
    sa.column("id", sa.Integer),
    sa.column("role_type_id", sa.Integer),
    sa.column("title", sa.String),
    sa.column("is_active", sa.Boolean),
)

role_features_table = sa.table(
    "role_features",
    sa.column("role_id", sa.Integer),
    sa.column("feature_id", sa.Integer),
)

SEED_ROLES = [
    {
        "title": "Super Admin",
        "role_type_code": "super_admin",
        "feature_codenames": ["user_management", "role_management", "dashboard", "login_hours_management"],
    },
    {
        "title": "Admin",
        "role_type_code": "admin",
        "feature_codenames": ["user_management", "dashboard"],
    },
    {
        "title": "Manager",
        "role_type_code": "manager",
        "feature_codenames": ["user_management", "dashboard", "login_hours_management"],
    },
    {
        "title": "Lead",
        "role_type_code": "lead",
        "feature_codenames": ["dashboard", "login_hours_management"],
    },
    {
        "title": "Employee",
        "role_type_code": "employee",
        "feature_codenames": ["dashboard"],
    },
]


def upgrade():
    connection = op.get_bind()

    role_type_ids = dict(
        connection.execute(sa.select(role_types_table.c.code, role_types_table.c.id)).all()
    )
    feature_ids = dict(
        connection.execute(sa.select(features_table.c.codename, features_table.c.id)).all()
    )

    role_features_rows = []
    for seed in SEED_ROLES:
        role_id = connection.execute(
            roles_table.insert()
            .values(
                title=seed["title"],
                role_type_id=role_type_ids[seed["role_type_code"]],
                is_active=True,
            )
            .returning(roles_table.c.id)
        ).scalar_one()

        role_features_rows.extend(
            {"role_id": role_id, "feature_id": feature_ids[codename]}
            for codename in seed["feature_codenames"]
        )

    op.bulk_insert(role_features_table, role_features_rows)


def downgrade():
    connection = op.get_bind()

    titles = [seed["title"] for seed in SEED_ROLES]
    role_ids = [
        row[0]
        for row in connection.execute(
            sa.select(roles_table.c.id).where(roles_table.c.title.in_(titles))
        )
    ]

    if role_ids:
        connection.execute(
            role_features_table.delete().where(role_features_table.c.role_id.in_(role_ids))
        )
        connection.execute(roles_table.delete().where(roles_table.c.id.in_(role_ids)))
