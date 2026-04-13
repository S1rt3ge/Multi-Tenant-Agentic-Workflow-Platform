"""M5 tool registry - create tool_registry table

Revision ID: 0003_m5_tool_registry
Revises: 0002_m2_workflows
Create Date: 2026-04-14
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = '0003_m5_tool_registry'
down_revision: Union[str, None] = '0002_m2_workflows'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'tool_registry',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('description', sa.Text(), nullable=False, server_default=''),
        sa.Column('tool_type', sa.Text(), nullable=False),
        sa.Column('config', JSONB(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default=sa.text('true')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index('idx_tool_registry_tenant', 'tool_registry', ['tenant_id'])
    op.create_unique_constraint('uq_tool_registry_tenant_name', 'tool_registry', ['tenant_id', 'name'])


def downgrade() -> None:
    op.drop_constraint('uq_tool_registry_tenant_name', 'tool_registry', type_='unique')
    op.drop_index('idx_tool_registry_tenant', table_name='tool_registry')
    op.drop_table('tool_registry')
