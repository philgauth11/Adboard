"""add ad level columns

Revision ID: d0620082110b
Revises: 92e857064d35
Create Date: 2026-04-23 23:00:35.039300

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text


revision = 'd0620082110b'
down_revision = '92e857064d35'
branch_labels = None
depends_on = None


def _column_exists(table, column):
    conn = op.get_bind()
    result = conn.execute(text(
        "SELECT 1 FROM information_schema.columns "
        "WHERE table_name=:t AND column_name=:c"
    ), {"t": table, "c": column})
    return result.fetchone() is not None


def upgrade():
    if not _column_exists('ad_metrics', 'ad_id'):
        op.add_column('ad_metrics', sa.Column('ad_id', sa.String(length=50), nullable=True))
    if not _column_exists('ad_metrics', 'ad_name'):
        op.add_column('ad_metrics', sa.Column('ad_name', sa.String(length=200), nullable=True))


def downgrade():
    op.drop_column('ad_metrics', 'ad_name')
    op.drop_column('ad_metrics', 'ad_id')
