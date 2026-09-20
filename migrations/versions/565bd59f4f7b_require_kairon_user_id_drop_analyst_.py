"""require kairon user_id, drop analyst reviews

An upload row whose Coding Analyst name doesn't resolve to an existing
User is no longer saved at all (see app.kairon.services.import_batch) -
it's skipped and reported back to the uploader instead of being written
with a null user_id for a manager to resolve later. That makes user_id
mandatory on both kairon tables that carry it, and makes the
kairon_analyst_reviews human-in-the-loop queue (and its resolve
endpoint) dead: no code path creates a review anymore.

Any row already sitting with a null user_id (necessarily still
"pending" - a resolved review would have back-filled user_id) predates
this rule and can no longer be represented, so it's purged along with
its analyst-action row before the NOT NULL constraint is added.

Revision ID: 565bd59f4f7b
Revises: 82576dbfb00b
Create Date: 2026-09-18 20:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '565bd59f4f7b'
down_revision = '82576dbfb00b'
branch_labels = None
depends_on = None


def upgrade():
    op.drop_table('kairon_analyst_reviews')

    op.execute(
        "DELETE FROM kairon_chart_analyst_actions "
        "WHERE chart_record_id IN (SELECT id FROM kairon_chart_records WHERE user_id IS NULL)"
    )
    op.execute("DELETE FROM kairon_chart_records WHERE user_id IS NULL")

    op.alter_column('kairon_chart_records', 'user_id', existing_type=sa.Integer(), nullable=False)
    op.alter_column('kairon_chart_analyst_actions', 'user_id', existing_type=sa.Integer(), nullable=False)


def downgrade():
    op.alter_column('kairon_chart_analyst_actions', 'user_id', existing_type=sa.Integer(), nullable=True)
    op.alter_column('kairon_chart_records', 'user_id', existing_type=sa.Integer(), nullable=True)

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
    # Purged rows (upgrade()) are not restored - this only recreates the schema.
