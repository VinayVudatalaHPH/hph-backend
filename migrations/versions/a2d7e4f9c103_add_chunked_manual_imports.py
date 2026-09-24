"""add chunked manual imports

Revision ID: a2d7e4f9c103
Revises: f8a2c7d4e901
"""
from alembic import op
import sqlalchemy as sa


revision = "a2d7e4f9c103"
down_revision = "f8a2c7d4e901"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "manual_import_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("source_filename", sa.String(length=255), nullable=False),
        sa.Column("file_checksum", sa.String(length=64), nullable=False),
        sa.Column("uploaded_by_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(length=24), server_default="uploading", nullable=False),
        sa.Column("total_rows", sa.Integer(), nullable=False),
        sa.Column("processed_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unchanged_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "manual_import_chunks",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("batch_id", sa.Integer(), sa.ForeignKey("manual_import_batches.id"), nullable=False),
        sa.Column("chunk_number", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("created_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unchanged_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("batch_id", "chunk_number", name="uq_manual_import_chunk"),
    )

    connection = op.get_bind()
    role_exists = connection.execute(
        sa.text("SELECT 1 FROM pg_roles WHERE rolname = 'hph_app'")
    ).scalar()
    if role_exists:
        op.execute(
            "GRANT SELECT, INSERT, UPDATE, DELETE ON manual_import_batches, manual_import_chunks TO hph_app"
        )
        op.execute(
            "GRANT USAGE, SELECT ON SEQUENCE manual_import_batches_id_seq, manual_import_chunks_id_seq TO hph_app"
        )


def downgrade():
    op.drop_table("manual_import_chunks")
    op.drop_table("manual_import_batches")
