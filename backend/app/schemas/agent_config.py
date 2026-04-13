from datetime import datetime
from uuid import UUID
from typing import Any

from pydantic import BaseModel, Field


VALID_ROLES = {"retriever", "analyzer", "validator", "escalator", "custom"}
VALID_MODELS = {"gpt-4o", "gpt-4o-mini", "claude-sonnet", "claude-opus"}
VALID_MEMORY_TYPES = {"buffer", "summary", "vector"}


# --- Request schemas ---


class AgentConfigCreate(BaseModel):
    node_id: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    role: str = Field(default="analyzer")
    system_prompt: str = Field(default="You are a helpful assistant.")
    model: str = Field(default="gpt-4o")
    tools: list[dict[str, Any]] = Field(default_factory=list)
    memory_type: str = Field(default="buffer")
    max_tokens: int = Field(default=4096, ge=256, le=16384)
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)


class AgentConfigUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=255)
    role: str | None = None
    system_prompt: str | None = None
    model: str | None = None
    tools: list[dict[str, Any]] | None = None
    memory_type: str | None = None
    max_tokens: int | None = Field(None, ge=256, le=16384)
    temperature: float | None = Field(None, ge=0.0, le=2.0)


# --- Response schemas ---


class AgentConfigResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    workflow_id: UUID
    node_id: str
    name: str
    role: str
    system_prompt: str
    model: str
    tools: list[dict[str, Any]]
    memory_type: str
    max_tokens: int
    temperature: float
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
