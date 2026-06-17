"""m12 dispatch automation worker runs

Revision ID: 0017_m12_dispatch_automation_worker_runs
Revises: 0016_m12_dispatch_automation_plan_execution
Create Date: 2026-05-25 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0017_m12_dispatch_automation_worker_runs"
down_revision: str | None = "0016_m12_dispatch_automation_plan_execution"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "dispatch_automation_worker_config",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.create_table(
        "dispatch_automation_worker_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("triggered_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("trigger_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("limit", sa.Integer(), nullable=False),
        sa.Column("claimed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("executed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("blocked", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["triggered_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_dispatch_automation_worker_runs_tenant_created",
        "dispatch_automation_worker_runs",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "idx_dispatch_automation_worker_runs_tenant_trigger",
        "dispatch_automation_worker_runs",
        ["tenant_id", "trigger_type", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_dispatch_automation_worker_runs_tenant_trigger",
        table_name="dispatch_automation_worker_runs",
    )
    op.drop_index(
        "idx_dispatch_automation_worker_runs_tenant_created",
        table_name="dispatch_automation_worker_runs",
    )
    op.drop_table("dispatch_automation_worker_runs")
    op.drop_column("tenants", "dispatch_automation_worker_config")
