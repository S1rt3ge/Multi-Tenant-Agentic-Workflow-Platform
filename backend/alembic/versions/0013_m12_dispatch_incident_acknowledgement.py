"""m12 dispatch incident acknowledgement

Revision ID: 0013_m12_dispatch_incident_acknowledgement
Revises: 0012_m12_dispatch_alert_delivery
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID


revision = "0013_m12_dispatch_incident_acknowledgement"
down_revision = "0012_m12_dispatch_alert_delivery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "dispatch_incident_acknowledgements",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("tenant_id", UUID(as_uuid=True), nullable=False),
        sa.Column("incident_key", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="acknowledged"),
        sa.Column("severity", sa.Text(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("alert_codes", JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("acknowledged_by", UUID(as_uuid=True), nullable=True),
        sa.Column("acknowledged_by_email", sa.Text(), nullable=False),
        sa.Column("acknowledged_by_name", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["acknowledged_by"], ["users.id"]),
    )
    op.create_index(
        "idx_dispatch_incident_ack_tenant_key",
        "dispatch_incident_acknowledgements",
        ["tenant_id", "incident_key", "status"],
    )
    op.create_index(
        "idx_dispatch_incident_ack_tenant_created",
        "dispatch_incident_acknowledgements",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "idx_dispatch_incident_ack_tenant_created",
        table_name="dispatch_incident_acknowledgements",
    )
    op.drop_index(
        "idx_dispatch_incident_ack_tenant_key",
        table_name="dispatch_incident_acknowledgements",
    )
    op.drop_table("dispatch_incident_acknowledgements")
