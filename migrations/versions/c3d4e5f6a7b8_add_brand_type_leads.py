"""add brand_type to clients, leads to ad_metrics

Revision ID: c3d4e5f6a7b8
Revises: a1b2c3d4e5f6
Create Date: 2026-05-20 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'c3d4e5f6a7b8'
down_revision = 'a1b2c3d4e5f6'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('clients') as batch_op:
        batch_op.add_column(sa.Column('brand_type', sa.String(20), nullable=False, server_default='leadgen'))

    with op.batch_alter_table('ad_metrics') as batch_op:
        batch_op.add_column(sa.Column('leads', sa.Integer(), nullable=False, server_default='0'))


def downgrade():
    with op.batch_alter_table('ad_metrics') as batch_op:
        batch_op.drop_column('leads')

    with op.batch_alter_table('clients') as batch_op:
        batch_op.drop_column('brand_type')
