"""M4 execution engine - create executions and execution_logs tables

Revision ID: 0005_m4_executions
Revises: 0004_m3_agent_configs
Create Date: 2026-04-14
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

# revision identifiers, used by Alembic.
revision: str = '0005_m4_executions'
down_revision: Union[str, None] = '0004_m3_agent_configs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- executions ---
    op.create_table(
        'executions',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('tenant_id', UUID(as_uuid=True), sa.ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False),
        sa.Column('workflow_id', UUID(as_uuid=True), sa.ForeignKey('workflows.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.Text(), nullable=False, server_default='pending'),
        sa.Column('input_data', JSONB(), nullable=True),
        sa.Column('output_data', JSONB(), nullable=True),
        sa.Column('total_tokens', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('total_cost', sa.Float(), nullable=False, server_default=sa.text('0.0')),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('completed_at', sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index('idx_executions_tenant', 'executions', ['tenant_id'])
    op.create_index('idx_executions_workflow', 'executions', ['workflow_id'])
    op.create_index('idx_executions_status', 'executions', ['tenant_id', 'status'])
    op.create_index('idx_executions_created', 'executions', ['tenant_id', 'created_at'])

    # --- execution_logs ---
    op.create_table(
        'execution_logs',
        sa.Column('id', UUID(as_uuid=True), primary_key=True, server_default=sa.text('gen_random_uuid()')),
        sa.Column('execution_id', UUID(as_uuid=True), sa.ForeignKey('executions.id', ondelete='CASCADE'), nullable=False),
        sa.Column('agent_config_id', UUID(as_uuid=True), sa.ForeignKey('agent_configs.id'), nullable=True),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('agent_name', sa.Text(), nullable=False),
        sa.Column('action', sa.Text(), nullable=False),
        sa.Column('input_data', JSONB(), nullable=True),
        sa.Column('output_data', JSONB(), nullable=True),
        sa.Column('tokens_used', sa.Integer(), nullable=False, server_default=sa.text('0')),
        sa.Column('cost', sa.Float(), nullable=False, server_default=sa.text('0.0')),
        sa.Column('decision_reasoning', sa.Text(), nullable=True),
        sa.Column('duration_ms', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index('idx_execution_logs_execution', 'execution_logs', ['execution_id'])
    op.create_index('idx_execution_logs_step', 'execution_logs', ['execution_id', 'step_number'])


def downgrade() -> None:
    op.drop_index('idx_execution_logs_step', table_name='execution_logs')
    op.drop_index('idx_execution_logs_execution', table_name='execution_logs')
    op.drop_table('execution_logs')

    op.drop_index('idx_executions_created', table_name='executions')
    op.drop_index('idx_executions_status', table_name='executions')
    op.drop_index('idx_executions_workflow', table_name='executions')
    op.drop_index('idx_executions_tenant', table_name='executions')
    op.drop_table('executions')
