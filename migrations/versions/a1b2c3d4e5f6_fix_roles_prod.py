"""fix roles in prod — ensure no legacy superadmin/user roles remain

Revision ID: a1b2c3d4e5f6
Revises: f7a8b9c0d1e2
Create Date: 2026-05-06 12:00:00.000000

"""
from alembic import op

revision = 'a1b2c3d4e5f6'
down_revision = 'f7a8b9c0d1e2'
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "UPDATE team_members SET role = 'admin' "
        "WHERE role NOT IN ('admin', 'client')"
    )


def downgrade():
    pass
