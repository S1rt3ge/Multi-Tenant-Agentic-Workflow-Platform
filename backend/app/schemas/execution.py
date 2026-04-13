from datetime import datetime
from uuid import UUID
from typing import Any

from pydantic import BaseModel, Field


VALID_EXECUTION_STATUSES = {"pending", "running", "completed", "failed", "cancelled"}


# --- Request schemas ---


class ExecutionCreate(BaseModel):
    input_data: dict[str, Any] | None = Field(None, description="Input data for the workflow execution")


class ExecutionListQuery(BaseModel):
    workflow_id: UUID | None = None
    status: str | None = None
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=20, ge=1, le=100)


# --- Response schemas ---


class ExecutionStartResponse(BaseModel):
    execution_id: UUID
    status: str

    model_config = {"from_attributes": True}


class ExecutionLogResponse(BaseModel):
    id: UUID
    execution_id: UUID
    agent_config_id: UUID | None
    step_number: int
    agent_name: str
    action: str
    input_data: dict[str, Any] | None
    output_data: dict[str, Any] | None
    tokens_used: int
    cost: float
    decision_reasoning: str | None
    duration_ms: int | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExecutionResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    workflow_id: UUID
    status: str
    input_data: dict[str, Any] | None
    output_data: dict[str, Any] | None
    total_tokens: int
    total_cost: float
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExecutionListResponse(BaseModel):
    items: list[ExecutionResponse]
    total: int
    page: int
    per_page: int


# --- WebSocket event schemas ---


class WSEvent(BaseModel):
    type: str  # step_start | step_complete | execution_complete | error
    data: dict[str, Any]
