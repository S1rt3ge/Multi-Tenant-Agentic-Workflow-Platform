"""m12 dispatch automation plans

Revision ID: 0015_m12_dispatch_automation_plans
Revises: 0014_m12_dispatch_incident_resolution
Create Date: 2026-05-21 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0015_m12_dispatch_automation_plans"
down_revision: str | None = "0014_m12_dispatch_incident_resolution"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dispatch_automation_plans",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("recommendation_code", sa.Text(), nullable=False),
        sa.Column("automation_type", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("priority", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("rationale", sa.Text(), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column(
            "blocked_by",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("requested_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("requested_by_email", sa.Text(), nullable=False),
        sa.Column("requested_by_name", sa.Text(), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by_email", sa.Text(), nullable=True),
        sa.Column("approved_by_name", sa.Text(), nullable=True),
        sa.Column("approved_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("rejected_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("rejected_by_email", sa.Text(), nullable=True),
        sa.Column("rejected_by_name", sa.Text(), nullable=True),
        sa.Column("rejection_note", sa.Text(), nullable=True),
        sa.Column("rejected_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["rejected_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_dispatch_automation_plans_tenant_status",
        "dispatch_automation_plans",
        ["tenant_id", "status", "created_at"],
    )
    op.create_index(
        "idx_dispatch_automation_plans_tenant_code",
        "dispatch_automation_plans",
        ["tenant_id", "recommendation_code", "status"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_dispatch_automation_plans_tenant_code",
        table_name="dispatch_automation_plans",
    )
    op.drop_index(
        "idx_dispatch_automation_plans_tenant_status",
        table_name="dispatch_automation_plans",
    )
    op.drop_table("dispatch_automation_plans")
