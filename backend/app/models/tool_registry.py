import uuid

from sqlalchemy import Column, Text, Boolean, ForeignKey, Index, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class ToolRegistry(Base):
    __tablename__ = "tool_registry"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
    )
    name = Column(Text, nullable=False)
    description = Column(Text, nullable=False, default="")
    tool_type = Column(Text, nullable=False)  # api | database | file_system
    config = Column(JSONB, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    tenant = relationship("Tenant", backref="tools")

    __table_args__ = (
        Index("idx_tool_registry_tenant", "tenant_id"),
        Index(
            "uq_tool_registry_tenant_name_active",
            "tenant_id",
            "name",
            unique=True,
            postgresql_where=(is_active == True),  # noqa: E712
            sqlite_where=(is_active == True),  # noqa: E712
        ),
    )
