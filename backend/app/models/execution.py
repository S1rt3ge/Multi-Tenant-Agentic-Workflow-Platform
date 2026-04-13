import uuid

from sqlalchemy import Column, Text, Integer, Float, ForeignKey, Index, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Execution(Base):
    __tablename__ = "executions"

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
    status = Column(Text, nullable=False, default="pending")  # pending | running | completed | failed | cancelled
    input_data = Column(JSONB, nullable=True)
    output_data = Column(JSONB, nullable=True)
    total_tokens = Column(Integer, nullable=False, default=0)
    total_cost = Column(Float, nullable=False, default=0.0)
    error_message = Column(Text, nullable=True)
    started_at = Column(TIMESTAMP(timezone=True), nullable=True)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    tenant = relationship("Tenant", backref="executions")
    workflow = relationship("Workflow", backref="executions")
    logs = relationship(
        "ExecutionLog",
        back_populates="execution",
        cascade="all, delete-orphan",
        order_by="ExecutionLog.step_number",
    )

    __table_args__ = (
        Index("idx_executions_tenant", "tenant_id"),
        Index("idx_executions_workflow", "workflow_id"),
        Index("idx_executions_status", "tenant_id", "status"),
        Index("idx_executions_created", "tenant_id", "created_at"),
    )


class ExecutionLog(Base):
    __tablename__ = "execution_logs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_config_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_configs.id"),
        nullable=True,
    )
    step_number = Column(Integer, nullable=False)
    agent_name = Column(Text, nullable=False)
    action = Column(Text, nullable=False)  # llm_call | tool_call | decision | error
    input_data = Column(JSONB, nullable=True)
    output_data = Column(JSONB, nullable=True)
    tokens_used = Column(Integer, nullable=False, default=0)
    cost = Column(Float, nullable=False, default=0.0)
    decision_reasoning = Column(Text, nullable=True)
    duration_ms = Column(Integer, nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    # Relationships
    execution = relationship("Execution", back_populates="logs")
    agent_config = relationship("AgentConfig", backref="execution_logs")

    __table_args__ = (
        Index("idx_execution_logs_execution", "execution_id"),
        Index("idx_execution_logs_step", "execution_id", "step_number"),
    )
