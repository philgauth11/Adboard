"""marques access redesign — unify users, drop client_users

Revision ID: f7a8b9c0d1e2
Revises: d0620082110b
Create Date: 2026-05-06 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

revision = 'f7a8b9c0d1e2'
down_revision = 'd0620082110b'
branch_labels = None
depends_on = None


def upgrade():
    # 1. Fusionner superadmin + user → admin
    op.execute("UPDATE team_members SET role = 'admin' WHERE role IN ('superadmin', 'user')")

    # 2. Migrer ClientUser → TeamMember avec role='client'
    # WHERE NOT EXISTS évite les conflits si l'email existe déjà dans team_members
    op.execute("""
        INSERT INTO team_members (email, name, role, password_hash, created_at)
        SELECT cu.email, cu.email, 'client', cu.password_hash, cu.created_at
        FROM client_users cu
        WHERE NOT EXISTS (
            SELECT 1 FROM team_members tm WHERE tm.email = cu.email
        )
    """)

    # 3. Supprimer la table client_users
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
