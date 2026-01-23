"""Add admin category & video management

Revision ID: 7f4986a10eb9
Revises: d2e7fc464ace
Create Date: 2025-12-25 17:19:58.693352
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7f4986a10eb9'
down_revision = 'd2e7fc464ace'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('category', schema=None) as batch_op:
        batch_op.create_unique_constraint('uq_category_name', ['name'])


def downgrade():
    with op.batch_alter_table('category', schema=None) as batch_op:
        batch_op.drop_constraint('uq_category_name', type_='unique')
