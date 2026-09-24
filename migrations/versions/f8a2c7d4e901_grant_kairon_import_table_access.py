"""grant application access to chunked Kairon import tables

Revision ID: f8a2c7d4e901
Revises: e7c4a1d9f032
Create Date: 2026-09-24 16:40:00.000000
"""

from alembic import op


revision = "f8a2c7d4e901"
down_revision = "e7c4a1d9f032"
branch_labels = None
depends_on = None


def upgrade():
    # Production migrations run as the database owner, while the API runs as
    # the deliberately restricted hph_app role. PostgreSQL does not inherit
    # table or sequence privileges for objects the owner creates later.
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hph_app') THEN
                GRANT SELECT, INSERT, UPDATE, DELETE
                    ON TABLE kairon_import_chunks, kairon_chart_history
                    TO hph_app;
                GRANT USAGE, SELECT
                    ON SEQUENCE kairon_import_chunks_id_seq, kairon_chart_history_id_seq
                    TO hph_app;
            END IF;
        END
        $$;
        """
    )


def downgrade():
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'hph_app') THEN
                REVOKE SELECT, INSERT, UPDATE, DELETE
                    ON TABLE kairon_import_chunks, kairon_chart_history
                    FROM hph_app;
                REVOKE USAGE, SELECT
                    ON SEQUENCE kairon_import_chunks_id_seq, kairon_chart_history_id_seq
                    FROM hph_app;
            END IF;
        END
        $$;
        """
    )
