"""M3 builder UI - create agent_configs table

Revision ID: 0004_m3_agent_configs
Revises: 0003_m5_tool_registry
Create Date: 2026-04-14
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = '0004_m3_agent_configs'
down_revision: Union[str, None] = '0003_m5_tool_registry'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'agent_configs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('workflow_id', UUID(as_uuid=True), sa.ForeignKey('workflows.id', ondelete='CASCADE'), nullable=False),
        sa.Column('node_id', sa.Text(), nullable=False),
        sa.Column('name', sa.Text(), nullable=False),
        sa.Column('role', sa.Text(), nullable=False, server_default='analyzer'),
        sa.Column('system_prompt', sa.Text(), nullable=False, server_default='You are a helpful assistant.'),
        sa.Column('model', sa.Text(), nullable=False, server_default='gpt-4o'),
        sa.Column('tools', JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column('memory_type', sa.Text(), nullable=False, server_default='buffer'),
        sa.Column('max_tokens', sa.Integer(), nullable=False, server_default=sa.text('4096')),
        sa.Column('temperature', sa.Float(), nullable=False, server_default=sa.text('0.7')),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index('idx_agent_configs_workflow', 'agent_configs', ['workflow_id'])
    op.create_index('idx_agent_configs_tenant', 'agent_configs', ['tenant_id'])
    op.create_unique_constraint('uq_agent_configs_workflow_node', 'agent_configs', ['workflow_id', 'node_id'])


def downgrade() -> None:
    op.drop_constraint('uq_agent_configs_workflow_node', 'agent_configs', type_='unique')
    op.drop_index('idx_agent_configs_tenant', table_name='agent_configs')
    op.drop_index('idx_agent_configs_workflow', table_name='agent_configs')
    op.drop_table('agent_configs')
