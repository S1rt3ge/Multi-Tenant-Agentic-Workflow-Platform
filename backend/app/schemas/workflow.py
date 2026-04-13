from datetime import datetime
from uuid import UUID
from typing import Any

from pydantic import BaseModel, Field


# --- Request schemas ---


class WorkflowCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    execution_pattern: str = Field(default="linear", pattern="^(linear|parallel|cyclic)$")


class WorkflowUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    definition: dict[str, Any] | None = None
    execution_pattern: str | None = Field(None, pattern="^(linear|parallel|cyclic)$")


# --- Response schemas ---


class WorkflowResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str
    definition: dict[str, Any]
    execution_pattern: str
    is_active: bool
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowListResponse(BaseModel):
    items: list[WorkflowResponse]
    total: int
    page: int
    per_page: int
