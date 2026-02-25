"""Add uploaded_by column to videos

Revision ID: a401c1ca38b8
Revises: 9b7234de17d2
Create Date: 2026-02-25 11:02:28.447051
"""

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a401c1ca38b8'
down_revision = '9b7234de17d2'
branch_labels = None
depends_on = None


def upgrade():
    # Add uploaded_by column to videos table
    with op.batch_alter_table('videos', schema=None) as batch_op:
        batch_op.add_column(sa.Column('uploaded_by', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_videos_uploaded_by_users",
            "users",
            ["uploaded_by"],
            ["id"],
            ondelete="SET NULL"
        )

    # Add role, password, created_at to users table safely
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('password', sa.String(length=200), nullable=False))
        batch_op.add_column(sa.Column('role', sa.String(length=20), nullable=True))
        batch_op.add_column(sa.Column('created_at', sa.DateTime(), nullable=True))
        batch_op.create_unique_constraint("uq_users_username", ['username'])


def downgrade():
    # Remove uploaded_by column from videos table
    with op.batch_alter_table('videos', schema=None) as batch_op:
        batch_op.drop_constraint("fk_videos_uploaded_by_users", type_='foreignkey')
        batch_op.drop_column('uploaded_by')

    # Remove role, password, created_at from users table
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.drop_constraint("uq_users_username", type_='unique')
        batch_op.drop_column('created_at')
        batch_op.drop_column('role')
        batch_op.drop_column('password')