import json
from uuid import UUID

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_tenant, require_role
from app.models.connector import WorkflowTrigger
from app.models.user import User
from app.schemas.connector import (
    ConnectorCredentialCreate,
    ConnectorCredentialListResponse,
    ConnectorCredentialResponse,
    ConnectorDetailResponse,
    ConnectorListResponse,
    WebhookIngestResponse,
    WorkflowTriggerCreate,
    WorkflowTriggerListResponse,
    WorkflowTriggerResponse,
)
from app.services import connector_service

router = APIRouter(tags=["connectors"])


def _webhook_url(request: Request, public_id: str) -> str:
    return f"{str(request.base_url).rstrip('/')}/api/v1/webhooks/{public_id}"


def _trigger_response(
    trigger: WorkflowTrigger,
    request: Request,
) -> WorkflowTriggerResponse:
    response = WorkflowTriggerResponse.model_validate(trigger)
    response.webhook_url = _webhook_url(request, trigger.public_id)
    return response


@router.get("/connectors", response_model=ConnectorListResponse)
async def list_connectors(
    _: User = Depends(get_current_user),
):
    return ConnectorListResponse(items=connector_service.list_connectors())


@router.get("/connectors/{connector_key}", response_model=ConnectorDetailResponse)
async def get_connector(
    connector_key: str,
    _: User = Depends(get_current_user),
):
    return ConnectorDetailResponse.model_validate(
        connector_service.get_connector(connector_key)
    )


@router.post(
    "/connector-credentials",
    response_model=ConnectorCredentialResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_connector_credential(
    data: ConnectorCredentialCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "editor")),
    tenant_id: UUID = Depends(get_current_tenant),
):
    credential = await connector_service.create_credential(
        db=db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        connector_key=data.connector_key,
        name=data.name,
        auth_type=data.auth_type,
        config=data.config,
    )
    return ConnectorCredentialResponse.model_validate(credential)


@router.get(
    "/connector-credentials",
    response_model=ConnectorCredentialListResponse,
)
async def list_connector_credentials(
    connector_key: str | None = None,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant),
):
    credentials = await connector_service.list_credentials(
        db=db,
        tenant_id=tenant_id,
        connector_key=connector_key,
    )
    return ConnectorCredentialListResponse(
        items=[ConnectorCredentialResponse.model_validate(item) for item in credentials]
    )


@router.delete("/connector-credentials/{credential_id}", status_code=204)
async def delete_connector_credential(
    credential_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("owner", "editor")),
    tenant_id: UUID = Depends(get_current_tenant),
):
    await connector_service.delete_credential(
        db=db,
        tenant_id=tenant_id,
        credential_id=credential_id,
    )


@router.post(
    "/workflows/{workflow_id}/triggers",
    response_model=WorkflowTriggerResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow_trigger(
    workflow_id: UUID,
    data: WorkflowTriggerCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "editor")),
    tenant_id: UUID = Depends(get_current_tenant),
):
    trigger = await connector_service.create_trigger(
        db=db,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        user_id=current_user.id,
        trigger_type=data.trigger_type,
        config=data.config,
    )
    return _trigger_response(trigger, request)


@router.get(
    "/workflows/{workflow_id}/triggers",
    response_model=WorkflowTriggerListResponse,
)
async def list_workflow_triggers(
    workflow_id: UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant),
):
    triggers = await connector_service.list_triggers(
        db=db,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
    )
    return WorkflowTriggerListResponse(
        items=[_trigger_response(trigger, request) for trigger in triggers]
    )


@router.post(
    "/webhooks/{public_trigger_id}",
    response_model=WebhookIngestResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def ingest_webhook(
    public_trigger_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    # Read the raw body so HMAC signatures are verified over the exact bytes
    # the client signed, then parse JSON for the execution payload.
    raw_body = await request.body()
    if raw_body:
        try:
            payload = json.loads(raw_body)
        except (ValueError, TypeError):
            payload = {}
    else:
        payload = {}
    if not isinstance(payload, dict):
        payload = {"data": payload}
    result = await connector_service.ingest_webhook(
        db=db,
        public_trigger_id=public_trigger_id,
        payload=payload,
        headers=dict(request.headers),
        raw_body=raw_body,
    )
    return WebhookIngestResponse(
        execution_id=result.execution_id,
        status=result.status,
    )
