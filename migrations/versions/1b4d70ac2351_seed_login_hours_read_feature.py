"""seed login hours read feature

Revision ID: 1b4d70ac2351
Revises: 0a3c6f9b1240
Create Date: 2026-09-19 19:15:00.000000

"""
from alembic import op
import sqlalchemy as sa


revision = "1b4d70ac2351"
down_revision = "0a3c6f9b1240"
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
roles = sa.table("roles", sa.column("id", sa.Integer), sa.column("title", sa.String))
role_features = sa.table(
    "role_features",
    sa.column("role_id", sa.Integer),
    sa.column("feature_id", sa.Integer),
)


def upgrade():
    connection = op.get_bind()
    feature_id = connection.execute(
        features.insert()
        .values(
            codename="login_hours",
            title="Login Hours",
            description="View login-hour records within the user's reporting scope.",
            active=True,
        )
        .returning(features.c.id)
    ).scalar_one()
    role_ids = [
        row[0]
        for row in connection.execute(
            sa.select(roles.c.id).where(roles.c.title.in_(("Manager", "Lead", "Employee")))
        )
    ]
    if role_ids:
        op.bulk_insert(
            role_features,
            [{"role_id": role_id, "feature_id": feature_id} for role_id in role_ids],
        )


def downgrade():
    connection = op.get_bind()
    feature_id = connection.execute(
        sa.select(features.c.id).where(features.c.codename == "login_hours")
    ).scalar_one_or_none()
    if feature_id is not None:
        connection.execute(role_features.delete().where(role_features.c.feature_id == feature_id))
        connection.execute(features.delete().where(features.c.id == feature_id))
