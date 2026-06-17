"""m12 dispatch incident resolution

Revision ID: 0014_m12_dispatch_incident_resolution
Revises: 0013_m12_dispatch_incident_acknowledgement
Create Date: 2026-05-18
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID


revision = "0014_m12_dispatch_incident_resolution"
down_revision = "0013_m12_dispatch_incident_acknowledgement"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "dispatch_incident_acknowledgements",
        sa.Column("resolved_by", UUID(as_uuid=True), nullable=True),
    )
    op.add_column(
        "dispatch_incident_acknowledgements",
        sa.Column("resolved_by_email", sa.Text(), nullable=True),
    )
    op.add_column(
        "dispatch_incident_acknowledgements",
        sa.Column("resolved_by_name", sa.Text(), nullable=True),
    )
    op.add_column(
        "dispatch_incident_acknowledgements",
        sa.Column("resolution_note", sa.Text(), nullable=True),
    )
    op.add_column(
        "dispatch_incident_acknowledgements",
        sa.Column("resolved_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_dispatch_incident_ack_resolved_by",
        "dispatch_incident_acknowledgements",
        "users",
        ["resolved_by"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_dispatch_incident_ack_resolved_by",
        "dispatch_incident_acknowledgements",
        type_="foreignkey",
    )
    op.drop_column("dispatch_incident_acknowledgements", "resolved_at")
    op.drop_column("dispatch_incident_acknowledgements", "resolution_note")
    op.drop_column("dispatch_incident_acknowledgements", "resolved_by_name")
    op.drop_column("dispatch_incident_acknowledgements", "resolved_by_email")
    op.drop_column("dispatch_incident_acknowledgements", "resolved_by")
