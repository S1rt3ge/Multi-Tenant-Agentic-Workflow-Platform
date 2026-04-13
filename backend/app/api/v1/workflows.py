from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_tenant, require_role
from app.models.user import User
from app.schemas.workflow import (
    WorkflowCreate,
    WorkflowUpdate,
    WorkflowResponse,
    WorkflowListResponse,
)
from app.services import workflow_service

router = APIRouter(prefix="/workflows", tags=["workflows"])


@router.post("/", response_model=WorkflowResponse, status_code=201)
async def create_workflow(
    data: WorkflowCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "editor")),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """Create a new workflow. Viewers cannot create."""
    workflow = await workflow_service.create_workflow(
        db=db,
        tenant_id=tenant_id,
        user_id=current_user.id,
        name=data.name,
        description=data.description,
        execution_pattern=data.execution_pattern,
    )
    return workflow


@router.get("/", response_model=WorkflowListResponse)
async def list_workflows(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    search: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """List all active workflows for the current tenant."""
    items, total = await workflow_service.list_workflows(
        db=db, tenant_id=tenant_id, page=page, per_page=per_page, search=search
    )
    return WorkflowListResponse(items=items, total=total, page=page, per_page=per_page)


@router.get("/{workflow_id}", response_model=WorkflowResponse)
async def get_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """Get a single workflow by ID."""
    workflow = await workflow_service.get_workflow(
        db=db, tenant_id=tenant_id, workflow_id=workflow_id
    )
    return workflow


@router.put("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: UUID,
    data: WorkflowUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "editor")),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """Update a workflow. Viewers cannot update."""
    workflow = await workflow_service.update_workflow(
        db=db,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        name=data.name,
        description=data.description,
        definition=data.definition,
        execution_pattern=data.execution_pattern,
    )
    return workflow


@router.post("/{workflow_id}/duplicate", response_model=WorkflowResponse, status_code=201)
async def duplicate_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "editor")),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """Duplicate a workflow. Viewers cannot duplicate."""
    workflow = await workflow_service.duplicate_workflow(
        db=db, tenant_id=tenant_id, user_id=current_user.id, workflow_id=workflow_id
    )
    return workflow


@router.delete("/{workflow_id}", status_code=204)
async def delete_workflow(
    workflow_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "editor")),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """Soft-delete a workflow. Viewers cannot delete."""
    await workflow_service.delete_workflow(
        db=db, tenant_id=tenant_id, workflow_id=workflow_id
    )
