"""M1 auth and tenants - create tenants and users tables

Revision ID: 0001_m1_auth_tenants
Revises: 
Create Date: 2026-04-14
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

# revision identifiers, used by Alembic.
revision: str = '0001_m1_auth_tenants'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- tenants ---
    op.create_table(
        'tenants',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('slug', sa.Text(), nullable=False),
        sa.Column('plan', sa.Text(), nullable=False, server_default='free'),
        sa.Column('max_workflows', sa.Integer(), nullable=False, server_default='2'),
        sa.Column('max_agents_per_workflow', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('monthly_token_budget', sa.Integer(), nullable=False, server_default='100000'),
        sa.Column('tokens_used_this_month', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('slug', name='uq_tenants_slug'),
    )

    # --- users ---
    op.create_table(
        'users',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('email', sa.Text(), nullable=False),
        sa.Column('password_hash', sa.Text(), nullable=False),
        sa.Column('full_name', sa.Text(), nullable=True),
        sa.Column('role', sa.Text(), nullable=False, server_default='editor'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint('email', name='uq_users_email'),
    )

    # --- indexes ---
    op.create_index('idx_users_tenant_id', 'users', ['tenant_id'])
    op.create_index('idx_users_email', 'users', ['email'])


def downgrade() -> None:
    op.drop_index('idx_users_email', table_name='users')
    op.drop_index('idx_users_tenant_id', table_name='users')
    op.drop_table('users')
    op.drop_table('tenants')
