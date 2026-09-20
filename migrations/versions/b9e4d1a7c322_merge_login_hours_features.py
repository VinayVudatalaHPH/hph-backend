"""merge login hours features

Revision ID: b9e4d1a7c322
Revises: a8f3c9d2e611
"""

from alembic import op
import sqlalchemy as sa


revision = "b9e4d1a7c322"
down_revision = "a8f3c9d2e611"
branch_labels = None
depends_on = None


features = sa.table(
    "features",
    sa.column("id", sa.Integer),
    sa.column("codename", sa.String),
    sa.column("title", sa.String),
    sa.column("description", sa.Text),
    sa.column("active", sa.Boolean),
)
roles = sa.table(
    "roles",
    sa.column("id", sa.Integer),
    sa.column("role_type_id", sa.Integer),
)
role_types = sa.table(
    "role_types",
    sa.column("id", sa.Integer),
    sa.column("code", sa.String),
)
role_features = sa.table(
    "role_features",
    sa.column("role_id", sa.Integer),
    sa.column("feature_id", sa.Integer),
    sa.column("can_read", sa.Boolean),
    sa.column("can_write", sa.Boolean),
)


def _feature_id(connection, codename):
    return connection.execute(
        sa.select(features.c.id).where(features.c.codename == codename)
    ).scalar_one_or_none()


def upgrade():
    connection = op.get_bind()
    login_hours_id = _feature_id(connection, "login_hours")
    management_id = _feature_id(connection, "login_hours_management")

    connection.execute(
        features.update()
        .where(features.c.id == login_hours_id)
        .values(description="View login-hour records; write access allows Managers to upload attendance workbooks.")
    )

    role_rows = connection.execute(
        sa.select(roles.c.id, role_types.c.code).select_from(
            roles.join(role_types, roles.c.role_type_id == role_types.c.id)
        )
    ).all()
    for role_id, role_type_code in role_rows:
        if role_type_code not in {"manager", "lead", "employee"}:
            continue
        existing = connection.execute(
            sa.select(role_features.c.role_id).where(
                role_features.c.role_id == role_id,
                role_features.c.feature_id == login_hours_id,
            )
        ).first()
        values = {"can_read": True, "can_write": role_type_code == "manager"}
        if existing:
            connection.execute(
                role_features.update()
                .where(
                    role_features.c.role_id == role_id,
                    role_features.c.feature_id == login_hours_id,
                )
                .values(**values)
            )
        else:
            connection.execute(
                role_features.insert().values(
                    role_id=role_id,
                    feature_id=login_hours_id,
                    **values,
                )
            )

    if management_id is not None:
        connection.execute(role_features.delete().where(role_features.c.feature_id == management_id))
        connection.execute(features.delete().where(features.c.id == management_id))


def downgrade():
    connection = op.get_bind()
    login_hours_id = _feature_id(connection, "login_hours")
    connection.execute(
        features.update()
        .where(features.c.id == login_hours_id)
        .values(description="View login-hour records within the user's reporting scope.")
    )
    connection.execute(
        role_features.update()
        .where(role_features.c.feature_id == login_hours_id)
        .values(can_read=True, can_write=True)
    )

    management_id = connection.execute(
        features.insert()
        .values(
            codename="login_hours_management",
            title="Login Hours Management",
            description="Upload and manage login hours data.",
            active=True,
        )
        .returning(features.c.id)
    ).scalar_one()
    role_rows = connection.execute(
        sa.select(roles.c.id, role_types.c.code).select_from(
            roles.join(role_types, roles.c.role_type_id == role_types.c.id)
        )
    ).all()
    for role_id, role_type_code in role_rows:
        if role_type_code in {"super_admin", "manager", "lead"}:
            connection.execute(
                role_features.insert().values(
                    role_id=role_id,
                    feature_id=management_id,
                    can_read=True,
                    can_write=True,
                )
            )

