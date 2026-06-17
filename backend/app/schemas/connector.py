from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class ConnectorActionSummary(BaseModel):
    key: str
    name: str


class ConnectorResponse(BaseModel):
    key: str
    name: str
    description: str
    version: str
    auth_types: list[str]
    actions: list[ConnectorActionSummary]


class ConnectorDetailResponse(BaseModel):
    key: str
    name: str
    description: str
    version: str
    manifest: dict[str, Any]


class ConnectorListResponse(BaseModel):
    items: list[ConnectorResponse]


class ConnectorCredentialCreate(BaseModel):
    connector_key: str = Field(..., min_length=1, max_length=120)
    name: str = Field(..., min_length=1, max_length=255)
    auth_type: str = Field(..., min_length=1, max_length=120)
    config: dict[str, Any] = Field(...)


class ConnectorCredentialResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    connector_key: str
    name: str
    auth_type: str
    config_preview: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConnectorCredentialListResponse(BaseModel):
    items: list[ConnectorCredentialResponse]


class WorkflowTriggerCreate(BaseModel):
    trigger_type: str = Field(..., pattern="^(webhook|manual)$")
    config: dict[str, Any] = Field(default_factory=dict)


class WorkflowTriggerResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    workflow_id: UUID
    trigger_type: str
    public_id: str
    webhook_url: str | None = None
    config: dict[str, Any]
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class WorkflowTriggerListResponse(BaseModel):
    items: list[WorkflowTriggerResponse]


class WebhookIngestResponse(BaseModel):
    execution_id: UUID
    status: str
