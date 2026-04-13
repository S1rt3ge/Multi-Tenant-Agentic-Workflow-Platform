from datetime import datetime
from uuid import UUID
from typing import Any

from pydantic import BaseModel, Field


# --- Request schemas ---


class ToolCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = Field(default="", max_length=2000)
    tool_type: str = Field(..., pattern="^(api|database|file_system)$")
    config: dict[str, Any] = Field(...)


class ToolUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    description: str | None = Field(None, max_length=2000)
    tool_type: str | None = Field(None, pattern="^(api|database|file_system)$")
    config: dict[str, Any] | None = None


class ToolTestInput(BaseModel):
    test_input: str | None = None


# --- Response schemas ---


class ToolResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    name: str
    description: str
    tool_type: str
    config: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ToolTestResponse(BaseModel):
    success: bool
    response: Any = None
    latency_ms: float
