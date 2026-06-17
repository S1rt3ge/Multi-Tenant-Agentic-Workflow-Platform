import uuid

from sqlalchemy import Boolean, Column, ForeignKey, Index, Text, TIMESTAMP
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class Connector(Base):
    __tablename__ = "connectors"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    key = Column(Text, nullable=False, unique=True)
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=False, default="")
    version = Column(Text, nullable=False, default="1.0.0")
    manifest = Column(JSONB, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (Index("idx_connectors_active", "is_active"),)


class ConnectorCredential(Base):
    __tablename__ = "connector_credentials"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    connector_key = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    auth_type = Column(Text, nullable=False)
    encrypted_config = Column(JSONB, nullable=False)
    config_preview = Column(JSONB, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tenant = relationship("Tenant", backref="connector_credentials")
    creator = relationship("User", backref="created_connector_credentials")

    __table_args__ = (
        Index("idx_connector_credentials_tenant", "tenant_id"),
        Index("idx_connector_credentials_connector", "tenant_id", "connector_key"),
        Index(
            "uq_connector_credentials_tenant_name_active",
            "tenant_id",
            "name",
            unique=True,
            postgresql_where=(is_active == True),  # noqa: E712
            sqlite_where=(is_active == True),  # noqa: E712
        ),
    )


class WorkflowTrigger(Base):
    __tablename__ = "workflow_triggers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    trigger_type = Column(Text, nullable=False)
    public_id = Column(Text, nullable=False, unique=True)
    config = Column(JSONB, nullable=False, default=dict)
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tenant = relationship("Tenant", backref="workflow_triggers")
    workflow = relationship("Workflow", backref="triggers")
    creator = relationship("User", backref="created_workflow_triggers")

    __table_args__ = (
        Index("idx_workflow_triggers_workflow", "tenant_id", "workflow_id"),
        Index("idx_workflow_triggers_type", "tenant_id", "trigger_type"),
    )


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    workflow_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflows.id", ondelete="CASCADE"),
        nullable=False,
    )
    trigger_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_triggers.id", ondelete="CASCADE"),
        nullable=False,
    )
    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("executions.id", ondelete="SET NULL"),
        nullable=True,
    )
    payload = Column(JSONB, nullable=True)
    headers_sanitized = Column(JSONB, nullable=False, default=dict)
    status = Column(Text, nullable=False, default="received")
    error_message = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    tenant = relationship("Tenant", backref="webhook_events")
    workflow = relationship("Workflow", backref="webhook_events")
    trigger = relationship("WorkflowTrigger", backref="webhook_events")
    execution = relationship("Execution", backref="webhook_events")

    __table_args__ = (
        Index("idx_webhook_events_trigger", "tenant_id", "trigger_id", "created_at"),
        Index("idx_webhook_events_execution", "tenant_id", "execution_id"),
    )
