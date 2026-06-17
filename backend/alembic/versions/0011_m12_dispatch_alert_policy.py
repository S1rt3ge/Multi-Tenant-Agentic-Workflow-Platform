"""M12 dispatch alert policy

Revision ID: 0011_m12_dispatch_alert_policy
Revises: 0010_m12_workflow_dispatch_controls
Create Date: 2026-05-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB


revision: str = "0011_m12_dispatch_alert_policy"
down_revision: Union[str, None] = "0010_m12_workflow_dispatch_controls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "dispatch_alert_policy",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "dispatch_alert_policy")
