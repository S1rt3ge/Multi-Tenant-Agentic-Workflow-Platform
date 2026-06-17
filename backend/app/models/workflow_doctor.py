import uuid

from sqlalchemy import Column, Text, Float, ForeignKey, Index, TIMESTAMP
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class WorkflowFixSuggestion(Base):
    __tablename__ = "workflow_fix_suggestions"

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
    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
    )
    agent_config_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agent_configs.id", ondelete="SET NULL"),
        nullable=True,
    )
    tool_id = Column(
        UUID(as_uuid=True),
        ForeignKey("tool_registry.id", ondelete="SET NULL"),
        nullable=True,
    )
    detector_code = Column(Text, nullable=False)
    title = Column(Text, nullable=False)
    root_cause = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=False)
    severity = Column(Text, nullable=False, default="medium")
    confidence = Column(Float, nullable=False, default=0.0)
    patch = Column(JSONB, nullable=False, default=lambda: {"operations": []})
    replay_result = Column(JSONB, nullable=True)
    status = Column(Text, nullable=False, default="proposed")
    applied_by = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    applied_at = Column(TIMESTAMP(timezone=True), nullable=True)
    dismissed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(
        TIMESTAMP(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    tenant = relationship("Tenant", backref="workflow_fix_suggestions")
    workflow = relationship("Workflow", backref="fix_suggestions")
    execution = relationship("Execution", backref="fix_suggestions")
    agent_config = relationship("AgentConfig", backref="fix_suggestions")
    tool = relationship("ToolRegistry", backref="fix_suggestions")
    applied_by_user = relationship("User", backref="applied_fix_suggestions")

    __table_args__ = (
        Index("idx_fix_suggestions_tenant", "tenant_id"),
        Index("idx_fix_suggestions_execution", "execution_id"),
        Index("idx_fix_suggestions_status", "tenant_id", "status"),
        Index("idx_fix_suggestions_detector", "tenant_id", "detector_code"),
    )


class WorkflowReplayRun(Base):
    __tablename__ = "workflow_replay_runs"

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
    execution_id = Column(
        UUID(as_uuid=True),
        ForeignKey("executions.id", ondelete="CASCADE"),
        nullable=False,
    )
    suggestion_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workflow_fix_suggestions.id", ondelete="CASCADE"),
        nullable=False,
    )
    mode = Column(Text, nullable=False, default="validation_only")
    status = Column(Text, nullable=False, default="pending")
    result = Column(JSONB, nullable=False, default=dict)
    started_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)
    completed_at = Column(TIMESTAMP(timezone=True), nullable=True)
    created_at = Column(TIMESTAMP(timezone=True), server_default=func.now(), nullable=False)

    tenant = relationship("Tenant", backref="workflow_replay_runs")
    workflow = relationship("Workflow", backref="replay_runs")
    execution = relationship("Execution", backref="replay_runs")
    suggestion = relationship("WorkflowFixSuggestion", backref="replay_runs")

    __table_args__ = (
        Index("idx_replay_runs_tenant", "tenant_id"),
        Index("idx_replay_runs_suggestion", "suggestion_id"),
        Index("idx_replay_runs_status", "tenant_id", "status"),
    )
