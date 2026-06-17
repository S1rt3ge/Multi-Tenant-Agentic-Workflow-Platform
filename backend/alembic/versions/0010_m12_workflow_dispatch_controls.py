"""M12 workflow dispatch controls

Revision ID: 0010_m12_workflow_dispatch_controls
Revises: 0009_m9_connector_runtime
Create Date: 2026-05-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision: str = "0010_m12_workflow_dispatch_controls"
down_revision: Union[str, None] = "0009_m9_connector_runtime"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "workflows",
        sa.Column(
            "dispatch_paused",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "workflows",
        sa.Column("dispatch_paused_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.add_column(
        "workflows",
        sa.Column("dispatch_paused_by", UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_workflows_dispatch_paused_by_users",
        "workflows",
        "users",
        ["dispatch_paused_by"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_workflows_dispatch_paused_by_users",
        "workflows",
        type_="foreignkey",
    )
    op.drop_column("workflows", "dispatch_paused_by")
    op.drop_column("workflows", "dispatch_paused_at")
    op.drop_column("workflows", "dispatch_paused")
