"""seed kairon_management feature and assign it to the Manager role

Revision ID: 9adfac42aeb1
Revises: 781701f2e10d
Create Date: 2026-09-18 09:06:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9adfac42aeb1'
down_revision = '781701f2e10d'
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

FEATURE_CODENAME = "kairon_management"

# Per the requirement that updating Kairon data is a privilege only
# managers hold, this is attached only to the "Manager" starter role
# seeded by 2315bc38cac3 - not Admin or Super Admin. Broaden it later via
# POST /api/roles/{id}/features rather than another migration if that
# turns out to be too narrow.
GRANTED_TO_ROLE_TITLES = ("Manager",)


def upgrade():
    connection = op.get_bind()

    feature_id = connection.execute(
        features_table.insert()
        .values(
            codename=FEATURE_CODENAME,
            title="Kairon Chart Management",
            description="Bulk-upload Kairon chart-review records and resolve unmatched coding-analyst names.",
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
