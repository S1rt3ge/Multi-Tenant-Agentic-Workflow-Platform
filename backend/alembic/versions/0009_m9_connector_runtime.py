"""M9 connector runtime and webhook triggers

Revision ID: 0009_m9_connector_runtime
Revises: 0008_m8_workflow_doctor
Create Date: 2026-05-15
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "0009_m9_connector_runtime"
down_revision: Union[str, None] = "0008_m8_workflow_doctor"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "connectors",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("key", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("version", sa.Text(), nullable=False, server_default="1.0.0"),
        sa.Column("manifest", JSONB(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_connectors_active", "connectors", ["is_active"])

    op.create_table(
        "connector_credentials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("connector_key", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("auth_type", sa.Text(), nullable=False),
        sa.Column("encrypted_config", JSONB(), nullable=False),
        sa.Column("config_preview", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_connector_credentials_tenant", "connector_credentials", ["tenant_id"])
    op.create_index(
        "idx_connector_credentials_connector",
        "connector_credentials",
        ["tenant_id", "connector_key"],
    )
    op.create_index(
        "uq_connector_credentials_tenant_name_active",
        "connector_credentials",
        ["tenant_id", "name"],
        unique=True,
        postgresql_where=sa.text("is_active = true"),
    )

    op.create_table(
        "workflow_triggers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", UUID(as_uuid=True), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trigger_type", sa.Text(), nullable=False),
        sa.Column("public_id", sa.Text(), nullable=False, unique=True),
        sa.Column("config", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_workflow_triggers_workflow", "workflow_triggers", ["tenant_id", "workflow_id"])
    op.create_index("idx_workflow_triggers_type", "workflow_triggers", ["tenant_id", "trigger_type"])

    op.create_table(
        "webhook_events",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("workflow_id", UUID(as_uuid=True), sa.ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False),
        sa.Column("trigger_id", UUID(as_uuid=True), sa.ForeignKey("workflow_triggers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("execution_id", UUID(as_uuid=True), sa.ForeignKey("executions.id", ondelete="SET NULL"), nullable=True),
        sa.Column("payload", JSONB(), nullable=True),
        sa.Column("headers_sanitized", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("status", sa.Text(), nullable=False, server_default="received"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_webhook_events_trigger",
        "webhook_events",
        ["tenant_id", "trigger_id", "created_at"],
    )
    op.create_index("idx_webhook_events_execution", "webhook_events", ["tenant_id", "execution_id"])

    op.add_column("execution_logs", sa.Column("node_id", sa.Text(), nullable=True))
    op.add_column("execution_logs", sa.Column("node_type", sa.Text(), nullable=True))
    op.add_column("execution_logs", sa.Column("connector_key", sa.Text(), nullable=True))
    op.add_column("execution_logs", sa.Column("action_key", sa.Text(), nullable=True))
    op.add_column(
        "execution_logs",
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "execution_logs",
        sa.Column("retryable", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column("execution_logs", sa.Column("sanitized_error", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("execution_logs", "sanitized_error")
    op.drop_column("execution_logs", "retryable")
    op.drop_column("execution_logs", "attempt")
    op.drop_column("execution_logs", "action_key")
    op.drop_column("execution_logs", "connector_key")
    op.drop_column("execution_logs", "node_type")
    op.drop_column("execution_logs", "node_id")

    op.drop_index("idx_webhook_events_execution", table_name="webhook_events")
    op.drop_index("idx_webhook_events_trigger", table_name="webhook_events")
    op.drop_table("webhook_events")

    op.drop_index("idx_workflow_triggers_type", table_name="workflow_triggers")
    op.drop_index("idx_workflow_triggers_workflow", table_name="workflow_triggers")
    op.drop_table("workflow_triggers")

    op.drop_index("uq_connector_credentials_tenant_name_active", table_name="connector_credentials")
    op.drop_index("idx_connector_credentials_connector", table_name="connector_credentials")
    op.drop_index("idx_connector_credentials_tenant", table_name="connector_credentials")
    op.drop_table("connector_credentials")

    op.drop_index("idx_connectors_active", table_name="connectors")
    op.drop_table("connectors")
