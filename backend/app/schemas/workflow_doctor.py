from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


VALID_REPLAY_MODES = {"validation_only"}


class DiagnoseRequest(BaseModel):
    force: bool = Field(default=False)


class ReplayRequest(BaseModel):
    mode: str = Field(default="validation_only")


class ApplySuggestionRequest(BaseModel):
    retry: bool = Field(default=True)


class FixSuggestionResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    workflow_id: UUID
    execution_id: UUID
    agent_config_id: UUID | None
    tool_id: UUID | None
    detector_code: str
    title: str
    root_cause: str
    recommendation: str
    severity: str
    confidence: float
    patch: dict[str, Any]
    replay_result: dict[str, Any] | None
    status: str
    applied_by: UUID | None
    applied_at: datetime | None
    dismissed_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class FixSuggestionListResponse(BaseModel):
    items: list[FixSuggestionResponse]
    total: int


class ReplayRunResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    workflow_id: UUID
    execution_id: UUID
    suggestion_id: UUID
    mode: str
    status: str
    result: dict[str, Any]
    started_at: datetime
    completed_at: datetime | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ApplySuggestionResponse(BaseModel):
    suggestion_id: UUID
    status: str
    retry_execution_id: UUID | None = None


class DismissSuggestionResponse(BaseModel):
    suggestion_id: UUID
    status: str
