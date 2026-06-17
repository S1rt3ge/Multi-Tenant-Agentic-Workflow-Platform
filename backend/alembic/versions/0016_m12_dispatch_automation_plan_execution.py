"""m12 dispatch automation plan execution fields

Revision ID: 0016_m12_dispatch_automation_plan_execution
Revises: 0015_m12_dispatch_automation_plans
Create Date: 2026-05-21 00:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision: str = "0016_m12_dispatch_automation_plan_execution"
down_revision: str | None = "0015_m12_dispatch_automation_plans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "dispatch_automation_plans",
        sa.Column(
            "execution_result",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )
    op.add_column(
        "dispatch_automation_plans",
        sa.Column("executed_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "dispatch_automation_plans",
        sa.Column("execution_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("dispatch_automation_plans", "execution_error")
    op.drop_column("dispatch_automation_plans", "executed_at")
    op.drop_column("dispatch_automation_plans", "execution_result")
