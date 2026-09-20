"""seed coding_project_dashboard feature and assign it to Super Admin, Admin, and Manager

Revision ID: 82576dbfb00b
Revises: b1aa69e48961
Create Date: 2026-09-18 18:01:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '82576dbfb00b'
down_revision = 'b1aa69e48961'
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

FEATURE_CODENAME = "coding_project_dashboard"

# Seeing every user's aggregated Kairon + Manual numbers is neither a
# write privilege nor "see your own data" - it's its own thing, granted to
# Super Admin, Admin, and Manager at launch. Lead and Employee only get
# the personal `reports` view (see seed_reports_feature). Named per-project
# (not a generic "project_dashboard") so a second project's dashboard can
# get its own feature later without overloading this one.
GRANTED_TO_ROLE_TITLES = ("Super Admin", "Admin", "Manager")


def upgrade():
    connection = op.get_bind()

    feature_id = connection.execute(
        features_table.insert()
        .values(
            codename=FEATURE_CODENAME,
            title="Coding Project Dashboard",
            description="View the all-users Kairon + Manual aggregate dashboard for the Coding project.",
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
