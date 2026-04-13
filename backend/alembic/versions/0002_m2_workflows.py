"""M2 workflow management - create workflows table

Revision ID: 0002_m2_workflows
Revises: 0001_m1_auth_tenants
Create Date: 2026-04-14
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = '0002_m2_workflows'
down_revision: Union[str, None] = '0001_m1_auth_tenants'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'workflows',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('definition', JSONB(), nullable=False, server_default=sa.text("'{\"nodes\": [], \"edges\": []}'::jsonb")),
        sa.Column('execution_pattern', sa.Text(), nullable=False, server_default='linear'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_by', UUID(as_uuid=True), sa.ForeignKey('users.id'), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index('idx_workflows_tenant_id', 'workflows', ['tenant_id'])
    op.create_index('idx_workflows_tenant_active', 'workflows', ['tenant_id', 'is_active'])


def downgrade() -> None:
    op.drop_index('idx_workflows_tenant_active', table_name='workflows')
    op.drop_index('idx_workflows_tenant_id', table_name='workflows')
    op.drop_table('workflows')
