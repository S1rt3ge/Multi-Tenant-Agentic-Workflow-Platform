"""
Execution service: business logic for execution CRUD operations.

Handles: create + start execution, list, get, get logs, cancel.
The actual graph execution is delegated to engine.executor.run_execution.
"""

from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func as sa_func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.execution import Execution, ExecutionLog
from app.models.workflow import Workflow
from app.models.tenant import Tenant
from app.engine.compiler import validate_definition, CompilationError
from app.engine.executor import request_cancel
from app.services.analytics_service import invalidate_tenant_cache


ACTIVE_EXECUTION_STATUSES = ("pending", "running")
PLAN_CONCURRENT_EXECUTION_LIMITS = {
    "free": 1,
    "pro": 5,
    "team": 20,
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_workflow(db: AsyncSession, tenant_id: UUID, workflow_id: UUID) -> Workflow:
    """Get workflow, verify tenant ownership and active status."""
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.tenant_id == tenant_id,
            Workflow.is_active == True,  # noqa: E712
        )
    )
    wf = result.scalar_one_or_none()
    if wf is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return wf


async def _get_execution(db: AsyncSession, tenant_id: UUID, execution_id: UUID) -> Execution:
    """Get execution by ID, verify tenant ownership."""
    result = await db.execute(
        select(Execution).where(
            Execution.id == execution_id,
            Execution.tenant_id == tenant_id,
        )
    )
    execution = result.scalar_one_or_none()
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    return execution


def _get_concurrent_execution_limit(plan: str | None) -> int:
    """Return the concurrent execution cap for a tenant plan."""
    return PLAN_CONCURRENT_EXECUTION_LIMITS.get((plan or "free").lower(), 1)


async def _count_active_executions(db: AsyncSession, tenant_id: UUID) -> int:
    """Count executions that currently consume a concurrency slot."""
    result = await db.execute(
        select(sa_func.count(Execution.id)).where(
            Execution.tenant_id == tenant_id,
            Execution.status.in_(ACTIVE_EXECUTION_STATUSES),
        )
    )
    return result.scalar() or 0


# ---------------------------------------------------------------------------
# Create execution (returns pending execution for background task to pick up)
# ---------------------------------------------------------------------------

async def create_execution(
    db: AsyncSession,
    tenant_id: UUID,
    workflow_id: UUID,
    input_data: dict | None,
) -> Execution:
    """Create a new execution record and validate prerequisites.

    Returns:
        Execution with status='pending'.

    Raises:
        HTTPException 400: Invalid graph definition.
        HTTPException 404: Workflow not found.
        HTTPException 422: Budget exceeded.
    """
    workflow = await _get_workflow(db, tenant_id, workflow_id)

    # Validate definition
    definition = workflow.definition
    if not definition or not definition.get("nodes"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Workflow has no nodes defined. Add agents in the Builder first.",
        )

    try:
        validate_definition(definition)
    except CompilationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid workflow graph: {str(e)}",
        )

    # Check budget
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id).with_for_update()
    )
    tenant = tenant_result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    if tenant.tokens_used_this_month >= tenant.monthly_token_budget:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Monthly token budget exceeded",
        )

    concurrent_limit = _get_concurrent_execution_limit(tenant.plan)
    active_execution_count = await _count_active_executions(db, tenant_id)
    if active_execution_count >= concurrent_limit:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Concurrent execution limit reached for plan '{tenant.plan}' "
                f"({concurrent_limit} active). Wait for a running execution to finish or upgrade your plan."
            ),
        )

    # Create execution
    execution = Execution(
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        status="pending",
        input_data=input_data,
    )
    db.add(execution)
    await db.commit()
    await db.refresh(execution)
    invalidate_tenant_cache(tenant_id)

    return execution


# ---------------------------------------------------------------------------
# List executions (paginated, filterable)
# ---------------------------------------------------------------------------

async def list_executions(
    db: AsyncSession,
    tenant_id: UUID,
    workflow_id: UUID | None = None,
    status_filter: str | None = None,
    page: int = 1,
    per_page: int = 20,
) -> dict:
    """List executions with pagination and optional filters.

    Returns:
        Dict with keys: items, total, page, per_page.
    """
    query = select(Execution).where(Execution.tenant_id == tenant_id)

    if workflow_id:
        query = query.where(Execution.workflow_id == workflow_id)

    if status_filter:
        valid_statuses = {"pending", "running", "completed", "failed", "cancelled"}
        if status_filter not in valid_statuses:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid status filter. Must be one of: {', '.join(sorted(valid_statuses))}",
            )
        query = query.where(Execution.status == status_filter)

    # Count total
    count_query = select(sa_func.count(Execution.id)).where(Execution.tenant_id == tenant_id)
    if workflow_id:
        count_query = count_query.where(Execution.workflow_id == workflow_id)
    if status_filter:
        count_query = count_query.where(Execution.status == status_filter)

    count_result = await db.execute(count_query)
    total = count_result.scalar() or 0

    # Paginate
    offset = (page - 1) * per_page
    query = query.order_by(desc(Execution.created_at)).offset(offset).limit(per_page)

    result = await db.execute(query)
    items = list(result.scalars().all())

    return {
        "items": items,
        "total": total,
        "page": page,
        "per_page": per_page,
    }


# ---------------------------------------------------------------------------
# Get single execution
# ---------------------------------------------------------------------------

async def get_execution(db: AsyncSession, tenant_id: UUID, execution_id: UUID) -> Execution:
    """Get a single execution by ID."""
    return await _get_execution(db, tenant_id, execution_id)


# ---------------------------------------------------------------------------
# Get execution logs
# ---------------------------------------------------------------------------

async def get_execution_logs(
    db: AsyncSession, tenant_id: UUID, execution_id: UUID
) -> list[ExecutionLog]:
    """Get all logs for an execution, ordered by step_number."""
    # Verify execution belongs to tenant
    await _get_execution(db, tenant_id, execution_id)

    result = await db.execute(
        select(ExecutionLog)
        .where(ExecutionLog.execution_id == execution_id)
        .order_by(ExecutionLog.step_number)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Cancel execution
# ---------------------------------------------------------------------------

async def cancel_execution(db: AsyncSession, tenant_id: UUID, execution_id: UUID) -> Execution:
    """Cancel a running execution.

    Raises:
        HTTPException 404: Execution not found.
        HTTPException 409: Execution is not running.
    """
    execution = await _get_execution(db, tenant_id, execution_id)

    if execution.status not in ("pending", "running"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot cancel execution with status '{execution.status}'. Only pending or running executions can be cancelled.",
        )

    # If running, flag for cancellation in the executor
    if execution.status == "running":
        if not request_cancel(str(execution_id)):
            refreshed = await _get_execution(db, tenant_id, execution_id)
            if refreshed.status not in ("pending", "running"):
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Cannot cancel execution with status '{refreshed.status}'. "
                        "Only pending or running executions can be cancelled."
                    ),
                )

    # For pending executions, cancel immediately
    if execution.status == "pending":
        from datetime import datetime, timezone
        execution.status = "cancelled"
        execution.error_message = "Execution cancelled by user"
        execution.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(execution)
        invalidate_tenant_cache(tenant_id)

    return execution
