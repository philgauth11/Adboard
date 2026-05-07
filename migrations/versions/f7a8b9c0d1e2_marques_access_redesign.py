"""marques access redesign — unify users, drop client_users

Revision ID: f7a8b9c0d1e2
Revises: d0620082110b
Create Date: 2026-05-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect

revision = 'f7a8b9c0d1e2'
down_revision = 'd0620082110b'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()

    # 1. Fusionner superadmin + user → admin
    op.execute("UPDATE team_members SET role = 'admin' WHERE role IN ('superadmin', 'user')")

    # 2 & 3. Migrer client_users → team_members puis supprimer la table
    # inspect() fonctionne sur SQLite et PostgreSQL (contrairement à information_schema)
    if 'client_users' in inspect(bind).get_table_names():
        bind.execute(sa.text("""
            INSERT INTO team_members (email, name, role, password_hash, created_at)
            SELECT cu.email, cu.email, 'client', cu.password_hash, cu.created_at
            FROM client_users cu
            WHERE NOT EXISTS (
                SELECT 1 FROM team_members tm WHERE tm.email = cu.email
            )
        """))
        op.drop_table('client_users')


def downgrade():
    op.create_table(
        'client_users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('client_id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=150), nullable=False),
        sa.Column('password_hash', sa.String(length=256), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_login_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['client_id'], ['clients.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
    )
