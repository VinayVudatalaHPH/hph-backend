"""consolidate dashboard and report features

Revision ID: a8f3c9d2e611
Revises: 7c2d96ef301a
"""

from alembic import op
import sqlalchemy as sa


revision = "a8f3c9d2e611"
down_revision = "7c2d96ef301a"
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


OBSOLETE_FEATURES = (
    "coding_project_dashboard",
    "kairon_management",
    "manual_daily_records_management",
)
REPORT_WRITERS = {"manager", "lead", "employee"}


def _feature_id(connection, codename):
    return connection.execute(
        sa.select(features.c.id).where(features.c.codename == codename)
    ).scalar_one()


def _ensure_assignment(connection, role_id, feature_id, can_write):
    existing = connection.execute(
        sa.select(role_features.c.role_id).where(
            role_features.c.role_id == role_id,
            role_features.c.feature_id == feature_id,
        )
    ).first()
    values = {"can_read": True, "can_write": can_write}
    if existing:
        connection.execute(
            role_features.update()
            .where(
                role_features.c.role_id == role_id,
                role_features.c.feature_id == feature_id,
            )
            .values(**values)
        )
    else:
        connection.execute(
            role_features.insert().values(
                role_id=role_id,
                feature_id=feature_id,
                **values,
            )
        )


def upgrade():
    connection = op.get_bind()
    dashboard_id = _feature_id(connection, "dashboard")
    reports_id = _feature_id(connection, "reports")

    connection.execute(
        features.update()
        .where(features.c.id == dashboard_id)
        .values(description="View the role-appropriate personal or team performance dashboard.")
    )
    connection.execute(
        features.update()
        .where(features.c.id == reports_id)
        .values(description="View Kairon and Manual reports and use the inputs available to the role.")
    )

    role_rows = connection.execute(
        sa.select(roles.c.id, role_types.c.code).select_from(
            roles.join(role_types, roles.c.role_type_id == role_types.c.id)
        )
    ).all()
    for role_id, role_type_code in role_rows:
        _ensure_assignment(connection, role_id, dashboard_id, False)
        _ensure_assignment(connection, role_id, reports_id, role_type_code in REPORT_WRITERS)

    obsolete_ids = [
        row[0]
        for row in connection.execute(
            sa.select(features.c.id).where(features.c.codename.in_(OBSOLETE_FEATURES))
        )
    ]
    if obsolete_ids:
        connection.execute(role_features.delete().where(role_features.c.feature_id.in_(obsolete_ids)))
        connection.execute(features.delete().where(features.c.id.in_(obsolete_ids)))


def downgrade():
    connection = op.get_bind()
    dashboard_id = _feature_id(connection, "dashboard")
    reports_id = _feature_id(connection, "reports")
    connection.execute(
        features.update()
        .where(features.c.id == dashboard_id)
        .values(description="Access to the dashboard views.")
    )
    connection.execute(
        features.update()
        .where(features.c.id == reports_id)
        .values(description="View your own Kairon and Manual daily records and submit a Manual log entry.")
    )
    connection.execute(
        role_features.update()
        .where(role_features.c.feature_id.in_((dashboard_id, reports_id)))
        .values(can_read=True, can_write=True)
    )

    legacy = (
        (
            "coding_project_dashboard",
            "Coding Project Dashboard",
            "View the all-users Kairon + Manual aggregate dashboard for the Coding project.",
            {"super_admin", "admin", "manager"},
        ),
        (
            "kairon_management",
            "Kairon Chart Management",
            "Bulk-upload Kairon chart-review records and resolve unmatched coding-analyst names.",
            {"manager"},
        ),
        (
            "manual_daily_records_management",
            "Manual Daily Records Management",
            "Approve or reject self-entered manual daily production/attendance records.",
            {"manager"},
        ),
    )
    role_rows = connection.execute(
        sa.select(roles.c.id, role_types.c.code).select_from(
            roles.join(role_types, roles.c.role_type_id == role_types.c.id)
        )
    ).all()
    for codename, title, description, granted_codes in legacy:
        feature_id = connection.execute(
            features.insert()
            .values(codename=codename, title=title, description=description, active=True)
            .returning(features.c.id)
        ).scalar_one()
        for role_id, role_type_code in role_rows:
            if role_type_code in granted_codes:
                connection.execute(
                    role_features.insert().values(
                        role_id=role_id,
                        feature_id=feature_id,
                        can_read=True,
                        can_write=True,
                    )
                )

