import uuid

from sqlalchemy import Column, Text, Boolean, ForeignKey, Index, Integer, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base

class Workflow(Base):
    __tablename__ = "workflows"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=False, default="")
    definition = Column(JSONB, nullable=False, default=lambda: {"nodes": [], "edges": []})
    execution_pattern = Column(Text, nullable=False, default="linear")  # linear | parallel | cyclic
    is_active = Column(Boolean, nullable=False, default=True)
    created_by = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id"),
        nullable=True,
    )
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    tenant = relationship("Tenant", backref="workflows")
    creator = relationship("User", backref="created_workflows")

    __table_args__ = (
        Index("idx_workflows_tenant_id", "tenant_id"),
        Index("idx_workflows_tenant_active", "tenant_id", "is_active"),
    )
