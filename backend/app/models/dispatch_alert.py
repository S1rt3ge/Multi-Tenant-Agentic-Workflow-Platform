import uuid

from sqlalchemy import Boolean, Column, Float, ForeignKey, Index, Integer, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class DispatchAlertChannelCredential(Base):
    __tablename__ = "dispatch_alert_channel_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(Text, nullable=False)
    channel_type = Column(Text, nullable=False)
    encrypted_config = Column(JSONB, nullable=False)
    config_preview = Column(JSONB, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tenant = relationship("Tenant", backref="dispatch_alert_channel_credentials")
    creator = relationship("User", backref="created_dispatch_alert_channel_credentials")

    __table_args__ = (
        Index("idx_dispatch_alert_channels_tenant", "tenant_id"),
        Index("idx_dispatch_alert_channels_type", "tenant_id", "channel_type"),
    )


class DispatchAlertDelivery(Base):
    __tablename__ = "dispatch_alert_deliveries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel_id = Column(
        UUID(as_uuid=True),
        ForeignKey("dispatch_alert_channel_credentials.id", ondelete="SET NULL"),
        nullable=True,
    )
    alert_code = Column(Text, nullable=False)
    channel_type = Column(Text, nullable=False)
    target_preview = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    status_code = Column(Integer, nullable=True)
    error_message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    tenant = relationship("Tenant", backref="dispatch_alert_deliveries")
    channel = relationship("DispatchAlertChannelCredential", backref="deliveries")

    __table_args__ = (
        Index("idx_dispatch_alert_deliveries_tenant", "tenant_id", "created_at"),
        Index("idx_dispatch_alert_deliveries_channel", "tenant_id", "channel_id"),
    )


class DispatchIncidentAcknowledgement(Base):
    __tablename__ = "dispatch_incident_acknowledgements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    incident_key = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="acknowledged")
    severity = Column(Text, nullable=False)
    summary = Column(Text, nullable=False)
    alert_codes = Column(JSONB, nullable=False, default=list)
    acknowledged_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    acknowledged_by_email = Column(Text, nullable=False)
    acknowledged_by_name = Column(Text, nullable=True)
    note = Column(Text, nullable=True)
    resolved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    resolved_by_email = Column(Text, nullable=True)
    resolved_by_name = Column(Text, nullable=True)
    resolution_note = Column(Text, nullable=True)
    resolved_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tenant = relationship("Tenant", backref="dispatch_incident_acknowledgements")
    owner = relationship(
        "User",
        foreign_keys=[acknowledged_by],
        backref="dispatch_incident_acknowledgements",
    )
    resolver = relationship("User", foreign_keys=[resolved_by])

    __table_args__ = (
        Index(
            "idx_dispatch_incident_ack_tenant_key",
            "tenant_id",
            "incident_key",
            "status",
        ),
        Index("idx_dispatch_incident_ack_tenant_created", "tenant_id", "created_at"),
    )


class DispatchAutomationPlan(Base):
    __tablename__ = "dispatch_automation_plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    recommendation_code = Column(Text, nullable=False)
    automation_type = Column(Text, nullable=False)
    status = Column(Text, nullable=False, default="pending_approval")
    priority = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    rationale = Column(Text, nullable=False)
    suggested_action = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False, default=0.0)
    evidence = Column(JSONB, nullable=False, default=list)
    blocked_by = Column(JSONB, nullable=False, default=list)
    requested_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    requested_by_email = Column(Text, nullable=False)
    requested_by_name = Column(Text, nullable=True)
    approved_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    approved_by_email = Column(Text, nullable=True)
    approved_by_name = Column(Text, nullable=True)
    approved_at = Column(TIMESTAMP(timezone=True), nullable=True)
    rejected_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    rejected_by_email = Column(Text, nullable=True)
    rejected_by_name = Column(Text, nullable=True)
    rejection_note = Column(Text, nullable=True)
    rejected_at = Column(TIMESTAMP(timezone=True), nullable=True)
    execution_result = Column(JSONB, nullable=False, default=dict)
    executed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    execution_error = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tenant = relationship("Tenant", backref="dispatch_automation_plans")
    requester = relationship("User", foreign_keys=[requested_by])
    approver = relationship("User", foreign_keys=[approved_by])
    rejector = relationship("User", foreign_keys=[rejected_by])

    __table_args__ = (
        Index(
            "idx_dispatch_automation_plans_tenant_status",
            "tenant_id",
            "status",
            "created_at",
        ),
        Index(
            "idx_dispatch_automation_plans_tenant_code",
            "tenant_id",
            "recommendation_code",
            "status",
        ),
    )


class DispatchAutomationWorkerRun(Base):
    __tablename__ = "dispatch_automation_worker_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    triggered_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    trigger_type = Column(Text, nullable=False)
    status = Column(Text, nullable=False)
    limit = Column(Integer, nullable=False)
    claimed = Column(Integer, nullable=False, default=0)
    executed = Column(Integer, nullable=False, default=0)
    blocked = Column(Integer, nullable=False, default=0)
    failed = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    tenant = relationship("Tenant", backref="dispatch_automation_worker_runs")
    actor = relationship("User", backref="dispatch_automation_worker_runs")

    __table_args__ = (
        Index(
            "idx_dispatch_automation_worker_runs_tenant_created",
            "tenant_id",
            "created_at",
        ),
        Index(
            "idx_dispatch_automation_worker_runs_tenant_trigger",
            "tenant_id",
            "trigger_type",
            "created_at",
        ),
    )
