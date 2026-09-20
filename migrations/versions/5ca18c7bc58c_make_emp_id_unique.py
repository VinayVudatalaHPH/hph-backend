"""make emp_id unique

Revision ID: 5ca18c7bc58c
Revises: f71c7e421834
Create Date: 2026-09-17 14:45:39.816583

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5ca18c7bc58c'
down_revision = 'f71c7e421834'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_users_emp_id', ['emp_id'])


def downgrade():
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint('uq_users_emp_id', type_='unique')
