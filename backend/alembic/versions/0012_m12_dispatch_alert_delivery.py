"""M12 dispatch alert delivery

Revision ID: 0012_m12_dispatch_alert_delivery
Revises: 0011_m12_dispatch_alert_policy
Create Date: 2026-05-17
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision: str = "0012_m12_dispatch_alert_delivery"
down_revision: Union[str, None] = "0011_m12_dispatch_alert_policy"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "dispatch_alert_channel_credentials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("channel_type", sa.Text(), nullable=False),
        sa.Column("encrypted_config", JSONB(), nullable=False),
        sa.Column("config_preview", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_dispatch_alert_channels_tenant",
        "dispatch_alert_channel_credentials",
        ["tenant_id"],
    )
    op.create_index(
        "idx_dispatch_alert_channels_type",
        "dispatch_alert_channel_credentials",
        ["tenant_id", "channel_type"],
    )

    op.create_table(
        "dispatch_alert_deliveries",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), sa.ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False),
        sa.Column(
            "channel_id",
            UUID(as_uuid=True),
            sa.ForeignKey("dispatch_alert_channel_credentials.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("alert_code", sa.Text(), nullable=False),
        sa.Column("channel_type", sa.Text(), nullable=False),
        sa.Column("target_preview", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False),
        sa.Column("status_code", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "idx_dispatch_alert_deliveries_tenant",
        "dispatch_alert_deliveries",
        ["tenant_id", "created_at"],
    )
    op.create_index(
        "idx_dispatch_alert_deliveries_channel",
        "dispatch_alert_deliveries",
        ["tenant_id", "channel_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_dispatch_alert_deliveries_channel", table_name="dispatch_alert_deliveries")
    op.drop_index("idx_dispatch_alert_deliveries_tenant", table_name="dispatch_alert_deliveries")
    op.drop_table("dispatch_alert_deliveries")
    op.drop_index("idx_dispatch_alert_channels_type", table_name="dispatch_alert_channel_credentials")
    op.drop_index("idx_dispatch_alert_channels_tenant", table_name="dispatch_alert_channel_credentials")
    op.drop_table("dispatch_alert_channel_credentials")
