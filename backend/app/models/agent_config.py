import uuid

from sqlalchemy import Column, Text, Integer, Float, ForeignKey, Index, UniqueConstraint, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class AgentConfig(Base):
    __tablename__ = "agent_configs"

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
    node_id = Column(Text, nullable=False)
    name = Column(Text, nullable=False)
    role = Column(Text, nullable=False, default="analyzer")
    system_prompt = Column(Text, nullable=False, default="You are a helpful assistant.")
    model = Column(Text, nullable=False, default="gpt-4o")
    tools = Column(JSONB, nullable=False, default=list)
    memory_type = Column(Text, nullable=False, default="buffer")
    max_tokens = Column(Integer, nullable=False, default=4096)
    temperature = Column(Float, nullable=False, default=0.7)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    # Relationships
    tenant = relationship("Tenant", backref="agent_configs")
    workflow = relationship("Workflow", backref="agent_configs")

    __table_args__ = (
        Index("idx_agent_configs_workflow", "workflow_id"),
        Index("idx_agent_configs_tenant", "tenant_id"),
        UniqueConstraint("workflow_id", "node_id", name="uq_agent_configs_workflow_node"),
    )
