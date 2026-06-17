from uuid import UUID

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_tenant, get_current_user, require_role
from app.models.user import User
from app.schemas.workflow_doctor import (
    ApplySuggestionRequest,
    ApplySuggestionResponse,
    DiagnoseRequest,
    DismissSuggestionResponse,
    FixSuggestionListResponse,
    FixSuggestionResponse,
    ReplayRequest,
    ReplayRunResponse,
)
from app.services import workflow_doctor_service

router = APIRouter(tags=["workflow-doctor"])


@router.post(
    "/executions/{execution_id}/diagnose",
    response_model=FixSuggestionListResponse,
    status_code=status.HTTP_201_CREATED,
)
async def diagnose_execution(
    execution_id: UUID,
    body: DiagnoseRequest = DiagnoseRequest(),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant),
):
    suggestions = await workflow_doctor_service.diagnose_execution(
        db=db,
        tenant_id=tenant_id,
        execution_id=execution_id,
        force=body.force,
    )
    return FixSuggestionListResponse(
        items=[FixSuggestionResponse.model_validate(item) for item in suggestions],
        total=len(suggestions),
    )


@router.get(
    "/executions/{execution_id}/fix-suggestions",
    response_model=FixSuggestionListResponse,
)
async def list_fix_suggestions(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant),
):
    suggestions = await workflow_doctor_service.list_suggestions(
        db=db,
        tenant_id=tenant_id,
        execution_id=execution_id,
    )
    return FixSuggestionListResponse(
        items=[FixSuggestionResponse.model_validate(item) for item in suggestions],
        total=len(suggestions),
    )


@router.post(
    "/fix-suggestions/{suggestion_id}/replay",
    response_model=ReplayRunResponse,
    status_code=status.HTTP_201_CREATED,
)
async def replay_fix_suggestion(
    suggestion_id: UUID,
    body: ReplayRequest = ReplayRequest(),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("owner", "editor")),
    tenant_id: UUID = Depends(get_current_tenant),
):
    replay_run = await workflow_doctor_service.replay_suggestion(
        db=db,
        tenant_id=tenant_id,
        suggestion_id=suggestion_id,
        mode=body.mode,
    )
    return ReplayRunResponse.model_validate(replay_run)


@router.post(
    "/fix-suggestions/{suggestion_id}/apply",
    response_model=ApplySuggestionResponse,
)
async def apply_fix_suggestion(
    suggestion_id: UUID,
    body: ApplySuggestionRequest = ApplySuggestionRequest(),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "editor")),
    tenant_id: UUID = Depends(get_current_tenant),
):
    result = await workflow_doctor_service.apply_suggestion(
        db=db,
        tenant_id=tenant_id,
        suggestion_id=suggestion_id,
        user_id=current_user.id,
        retry=body.retry,
    )
    return ApplySuggestionResponse(**result)


@router.post(
    "/fix-suggestions/{suggestion_id}/dismiss",
    response_model=DismissSuggestionResponse,
)
async def dismiss_fix_suggestion(
    suggestion_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("owner", "editor")),
    tenant_id: UUID = Depends(get_current_tenant),
):
    result = await workflow_doctor_service.dismiss_suggestion(
        db=db,
        tenant_id=tenant_id,
        suggestion_id=suggestion_id,
    )
    return DismissSuggestionResponse(**result)
