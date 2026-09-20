"""seed manual_daily_records_management feature and assign it to the Manager role

Revision ID: cd984d33a00f
Revises: 9b50545420c6
Create Date: 2026-09-18 17:01:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cd984d33a00f'
down_revision = '9b50545420c6'
branch_labels = None
depends_on = None

features_table = sa.table(
    "features",
    sa.column("id", sa.Integer),
    sa.column("codename", sa.String),
    sa.column("title", sa.String),
    sa.column("description", sa.Text),
    sa.column("active", sa.Boolean),
)

roles_table = sa.table(
    "roles",
    sa.column("id", sa.Integer),
    sa.column("title", sa.String),
)

role_features_table = sa.table(
    "role_features",
    sa.column("role_id", sa.Integer),
    sa.column("feature_id", sa.Integer),
)

FEATURE_CODENAME = "manual_daily_records_management"

# Per the requirement that reviewing (approving/rejecting) manual daily
# records is a manager-only privilege - not Admin or Super Admin at
# launch. Self-entry itself needs no feature grant; it's open to any
# logged-in user (enforced by the normal session baseline, not this flag).
GRANTED_TO_ROLE_TITLES = ("Manager",)


def upgrade():
    connection = op.get_bind()

    feature_id = connection.execute(
        features_table.insert()
        .values(
            codename=FEATURE_CODENAME,
            title="Manual Daily Records Management",
            description="Approve or reject self-entered manual daily production/attendance records.",
            active=True,
        )
        .returning(features_table.c.id)
    ).scalar_one()

    role_ids = [
        row[0]
        for row in connection.execute(
            sa.select(roles_table.c.id).where(roles_table.c.title.in_(GRANTED_TO_ROLE_TITLES))
        )
    ]
    if role_ids:
        op.bulk_insert(
            role_features_table,
            [{"role_id": role_id, "feature_id": feature_id} for role_id in role_ids],
        )


def downgrade():
    connection = op.get_bind()

    feature_id = connection.execute(
        sa.select(features_table.c.id).where(features_table.c.codename == FEATURE_CODENAME)
    ).scalar_one_or_none()

    if feature_id is not None:
        connection.execute(role_features_table.delete().where(role_features_table.c.feature_id == feature_id))
        connection.execute(features_table.delete().where(features_table.c.id == feature_id))
