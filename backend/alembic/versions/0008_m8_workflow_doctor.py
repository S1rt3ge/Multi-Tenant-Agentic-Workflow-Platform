"""M8 workflow doctor suggestions and replay runs

Revision ID: 0008_m8_workflow_doctor
Revises: 0007_refresh_tokens_tools
Create Date: 2026-05-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "0008_m8_workflow_doctor"
down_revision: Union[str, None] = "0007_refresh_tokens_tools"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "workflow_fix_suggestions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", UUID(as_uuid=True), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("execution_id", UUID(as_uuid=True), sa.ForeignKey("executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_config_id", UUID(as_uuid=True), sa.ForeignKey("agent_configs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("tool_id", UUID(as_uuid=True), sa.ForeignKey("tool_registry.id", ondelete="SET NULL"), nullable=True),
        sa.Column("detector_code", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("root_cause", sa.Text(), nullable=False),
        sa.Column("recommendation", sa.Text(), nullable=False),
        sa.Column("severity", sa.Text(), nullable=False, server_default="medium"),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="0"),
        sa.Column("patch", JSONB(), nullable=False, server_default=sa.text("""'{"operations": []}'::jsonb""")),
        sa.Column("replay_result", JSONB(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="proposed"),
        sa.Column("applied_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("applied_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("dismissed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_fix_suggestions_tenant", "workflow_fix_suggestions", ["tenant_id"])
    op.create_index("idx_fix_suggestions_execution", "workflow_fix_suggestions", ["execution_id"])
    op.create_index("idx_fix_suggestions_status", "workflow_fix_suggestions", ["tenant_id", "status"])
    op.create_index("idx_fix_suggestions_detector", "workflow_fix_suggestions", ["tenant_id", "detector_code"])

    op.create_table(
        "workflow_replay_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", UUID(as_uuid=True), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("execution_id", UUID(as_uuid=True), sa.ForeignKey("executions.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "suggestion_id",
            UUID(as_uuid=True),
            sa.ForeignKey("workflow_fix_suggestions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("mode", sa.Text(), nullable=False, server_default="validation_only"),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("result", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_replay_runs_tenant", "workflow_replay_runs", ["tenant_id"])
    op.create_index("idx_replay_runs_suggestion", "workflow_replay_runs", ["suggestion_id"])
    op.create_index("idx_replay_runs_status", "workflow_replay_runs", ["tenant_id", "status"])


def downgrade() -> None:
    op.drop_index("idx_replay_runs_status", table_name="workflow_replay_runs")
    op.drop_index("idx_replay_runs_suggestion", table_name="workflow_replay_runs")
    op.drop_index("idx_replay_runs_tenant", table_name="workflow_replay_runs")
    op.drop_table("workflow_replay_runs")

    op.drop_index("idx_fix_suggestions_detector", table_name="workflow_fix_suggestions")
    op.drop_index("idx_fix_suggestions_status", table_name="workflow_fix_suggestions")
    op.drop_index("idx_fix_suggestions_execution", table_name="workflow_fix_suggestions")
    op.drop_index("idx_fix_suggestions_tenant", table_name="workflow_fix_suggestions")
    op.drop_table("workflow_fix_suggestions")
