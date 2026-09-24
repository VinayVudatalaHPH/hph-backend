"""add chunked idempotent Kairon imports

Revision ID: e7c4a1d9f032
Revises: 4e6f91a2c8d0
Create Date: 2026-09-24 15:00:00.000000
"""

from alembic import op
import sqlalchemy as sa


revision = "e7c4a1d9f032"
down_revision = "4e6f91a2c8d0"
branch_labels = None
depends_on = None


def upgrade():
    op.alter_column("kairon_upload_batches", "as_of_date", existing_type=sa.Date(), nullable=True)
    op.add_column("kairon_upload_batches", sa.Column("status", sa.String(length=24), server_default="pending", nullable=False))
    op.add_column("kairon_upload_batches", sa.Column("file_checksum", sa.String(length=64), nullable=True))
    op.add_column("kairon_upload_batches", sa.Column("total_rows", sa.Integer(), server_default="0", nullable=False))
    op.add_column("kairon_upload_batches", sa.Column("processed_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("kairon_upload_batches", sa.Column("inserted_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("kairon_upload_batches", sa.Column("updated_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("kairon_upload_batches", sa.Column("unchanged_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("kairon_upload_batches", sa.Column("rejected_count", sa.Integer(), server_default="0", nullable=False))
    op.add_column("kairon_upload_batches", sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True))

    op.add_column("kairon_chart_records", sa.Column("chart_identity_hash", sa.String(length=64), nullable=True))
    op.add_column("kairon_chart_records", sa.Column("mbi_fingerprint", sa.String(length=64), nullable=True))
    op.add_column(
        "kairon_chart_records",
        sa.Column("first_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "kairon_chart_records",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.add_column(
        "kairon_chart_records",
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_unique_constraint("uq_kairon_chart_identity_hash", "kairon_chart_records", ["chart_identity_hash"])
    op.create_index("ix_kairon_chart_records_mbi_fingerprint", "kairon_chart_records", ["mbi_fingerprint"])

    op.create_table(
        "kairon_import_chunks",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("chunk_number", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=False),
        sa.Column("row_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("inserted_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("updated_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unchanged_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rejected_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("unmatched_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["kairon_upload_batches.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "chunk_number", name="uq_kairon_import_chunk"),
    )
    op.create_table(
        "kairon_chart_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("chart_record_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.Integer(), nullable=False),
        sa.Column("previous_status", sa.String(length=32), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("previous_user_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["batch_id"], ["kairon_upload_batches.id"]),
        sa.ForeignKeyConstraint(["chart_record_id"], ["kairon_chart_records.id"]),
        sa.ForeignKeyConstraint(["previous_user_id"], ["users.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )


def downgrade():
    op.drop_table("kairon_chart_history")
    op.drop_table("kairon_import_chunks")
    op.drop_index("ix_kairon_chart_records_mbi_fingerprint", table_name="kairon_chart_records")
    op.drop_constraint("uq_kairon_chart_identity_hash", "kairon_chart_records", type_="unique")
    for column in ("updated_at", "last_seen_at", "first_seen_at", "mbi_fingerprint", "chart_identity_hash"):
        op.drop_column("kairon_chart_records", column)
    for column in (
        "completed_at",
        "rejected_count",
        "unchanged_count",
        "updated_count",
        "inserted_count",
        "processed_count",
        "total_rows",
        "file_checksum",
        "status",
    ):
        op.drop_column("kairon_upload_batches", column)
    op.alter_column("kairon_upload_batches", "as_of_date", existing_type=sa.Date(), nullable=False)
