"""create manual daily records table

Revision ID: 9b50545420c6
Revises: 9adfac42aeb1
Create Date: 2026-09-18 17:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9b50545420c6'
down_revision = '9adfac42aeb1'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('manual_daily_records',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('record_date', sa.Date(), nullable=False),
    sa.Column('production_count', sa.Integer(), nullable=False),
    sa.Column('tech_issues_downtime_hours', sa.Numeric(precision=4, scale=2), nullable=False),
    sa.Column('no_inventory_idle_time_hours', sa.Numeric(precision=4, scale=2), nullable=False),
    sa.Column('leave_hours', sa.Numeric(precision=4, scale=2), nullable=False),
    sa.Column('meeting_engagement_hours', sa.Numeric(precision=4, scale=2), nullable=False),
    sa.Column('status', sa.String(length=16), nullable=False),
    sa.Column('reviewed_by_id', sa.Integer(), nullable=True),
    sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('rejection_reason', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.CheckConstraint('production_count >= 0', name='ck_manual_daily_records_production_count'),
    sa.CheckConstraint(
        'tech_issues_downtime_hours >= 0 AND tech_issues_downtime_hours <= 10',
        name='ck_manual_daily_records_tech_issues_downtime_hours',
    ),
    sa.CheckConstraint(
        'no_inventory_idle_time_hours >= 0 AND no_inventory_idle_time_hours <= 10',
        name='ck_manual_daily_records_no_inventory_idle_time_hours',
    ),
    sa.CheckConstraint('leave_hours >= 0 AND leave_hours <= 10', name='ck_manual_daily_records_leave_hours'),
    sa.CheckConstraint(
        'meeting_engagement_hours >= 0 AND meeting_engagement_hours <= 10',
        name='ck_manual_daily_records_meeting_engagement_hours',
    ),
    sa.CheckConstraint("status IN ('pending', 'approved', 'rejected')", name='ck_manual_daily_records_status'),
    sa.ForeignKeyConstraint(['reviewed_by_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('user_id', 'record_date', name='uq_manual_daily_records_user_date')
    )


def downgrade():
    op.drop_table('manual_daily_records')
