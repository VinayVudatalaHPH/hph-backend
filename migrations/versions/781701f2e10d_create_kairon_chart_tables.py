"""create kairon upload batches, chart records, analyst actions, and analyst reviews

Revision ID: 781701f2e10d
Revises: 68747ecf172a
Create Date: 2026-09-18 09:05:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '781701f2e10d'
down_revision = '68747ecf172a'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('kairon_upload_batches',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('as_of_date', sa.Date(), nullable=False),
    sa.Column('source_filename', sa.String(length=255), nullable=True),
    sa.Column('uploaded_by_id', sa.Integer(), nullable=False),
    sa.Column('uploaded_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('row_count', sa.Integer(), nullable=False),
    sa.Column('matched_count', sa.Integer(), nullable=False),
    sa.Column('unmatched_count', sa.Integer(), nullable=False),
    sa.Column('superseded_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('superseded_by_id', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['superseded_by_id'], ['kairon_upload_batches.id'], ),
    sa.ForeignKeyConstraint(['uploaded_by_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('kairon_chart_records',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('batch_id', sa.Integer(), nullable=False),
    sa.Column('program', sa.String(length=64), nullable=False),
    sa.Column('level', sa.String(length=16), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('coding_analyst_raw', sa.String(length=255), nullable=False),
    sa.Column('actions', sa.Integer(), nullable=False),
    sa.Column('last_action', sa.Text(), nullable=True),
    sa.Column('created_date', sa.Date(), nullable=False),
    sa.Column('completed_date', sa.Date(), nullable=True),
    sa.Column('tat_days', sa.Integer(), nullable=True),
    sa.Column('age_days', sa.Integer(), nullable=True),
    sa.Column('practice', sa.String(length=255), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("level IN ('1LR', '2LR', '3LR')", name='ck_kairon_chart_records_level'),
    sa.CheckConstraint("status IN ('Active', 'On Hold', 'Completed')", name='ck_kairon_chart_records_status'),
    sa.ForeignKeyConstraint(['batch_id'], ['kairon_upload_batches.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('kairon_chart_analyst_actions',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('chart_record_id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=True),
    sa.Column('level', sa.String(length=16), nullable=False),
    sa.Column('action_text', sa.Text(), nullable=True),
    sa.Column('action_date', sa.Date(), nullable=True),
    sa.Column('sequence_no', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['chart_record_id'], ['kairon_chart_records.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('kairon_analyst_reviews',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('chart_record_id', sa.Integer(), nullable=False),
    sa.Column('raw_name', sa.String(length=255), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('resolved_user_id', sa.Integer(), nullable=True),
    sa.Column('resolved_by_id', sa.Integer(), nullable=True),
    sa.Column('resolved_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint("status IN ('pending', 'resolved')", name='ck_kairon_analyst_reviews_status'),
    sa.ForeignKeyConstraint(['chart_record_id'], ['kairon_chart_records.id'], ),
    sa.ForeignKeyConstraint(['resolved_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['resolved_user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade():
    op.drop_table('kairon_analyst_reviews')
    op.drop_table('kairon_chart_analyst_actions')
    op.drop_table('kairon_chart_records')
    op.drop_table('kairon_upload_batches')
