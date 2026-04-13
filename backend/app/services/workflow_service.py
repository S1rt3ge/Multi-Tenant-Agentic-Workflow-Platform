import copy
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.tenant import Tenant
from app.models.workflow import Workflow


async def create_workflow(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    name: str,
    description: str,
    execution_pattern: str,
) -> Workflow:
    """Create a new workflow after checking tenant limits."""
    # Check tenant workflow limit
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_result.scalar_one()

    count_result = await db.execute(
        select(func.count())
        .select_from(Workflow)
        .where(Workflow.tenant_id == tenant_id, Workflow.is_active == True)  # noqa: E712
    )
    current_count = count_result.scalar()

    if current_count >= tenant.max_workflows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Workflow limit reached. Upgrade your plan.",
        )

    workflow = Workflow(
        tenant_id=tenant_id,
        name=name,
        description=description,
        execution_pattern=execution_pattern,
        created_by=user_id,
    )
    db.add(workflow)
    await db.commit()
    await db.refresh(workflow)
    return workflow


async def list_workflows(
    db: AsyncSession,
    tenant_id: UUID,
    page: int = 1,
    per_page: int = 20,
    search: str | None = None,
) -> tuple[list[Workflow], int]:
    """List active workflows for a tenant with pagination and search."""
    base_filter = [Workflow.tenant_id == tenant_id, Workflow.is_active == True]  # noqa: E712

    if search:
        base_filter.append(Workflow.name.ilike(f"%{search}%"))

    # Total count
    count_query = select(func.count()).select_from(Workflow).where(*base_filter)
    total = (await db.execute(count_query)).scalar()

    # Paginated items
    offset = (page - 1) * per_page
    items_query = (
        select(Workflow)
        .where(*base_filter)
        .order_by(Workflow.updated_at.desc())
        .offset(offset)
        .limit(per_page)
    )
    result = await db.execute(items_query)
    items = list(result.scalars().all())

    return items, total


async def get_workflow(db: AsyncSession, tenant_id: UUID, workflow_id: UUID) -> Workflow:
    """Get a single workflow by ID within tenant scope."""
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.tenant_id == tenant_id,
            Workflow.is_active == True,  # noqa: E712
        )
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found"
        )
    return workflow


async def update_workflow(
    db: AsyncSession,
    tenant_id: UUID,
    workflow_id: UUID,
    name: str | None = None,
    description: str | None = None,
    definition: dict | None = None,
    execution_pattern: str | None = None,
) -> Workflow:
    """Update a workflow. Full replace for definition (not merge)."""
    workflow = await get_workflow(db, tenant_id, workflow_id)

    if name is not None:
        workflow.name = name
    if description is not None:
        workflow.description = description
    if definition is not None:
        workflow.definition = definition
    if execution_pattern is not None:
        workflow.execution_pattern = execution_pattern

    await db.commit()
    await db.refresh(workflow)
    return workflow


async def duplicate_workflow(
    db: AsyncSession, tenant_id: UUID, user_id: UUID, workflow_id: UUID
) -> Workflow:
    """Duplicate a workflow with '(Copy)' suffix. Checks tenant limits."""
    original = await get_workflow(db, tenant_id, workflow_id)

    # Check tenant limit
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_result.scalar_one()

    count_result = await db.execute(
        select(func.count())
        .select_from(Workflow)
        .where(Workflow.tenant_id == tenant_id, Workflow.is_active == True)  # noqa: E712
    )
    current_count = count_result.scalar()

    if current_count >= tenant.max_workflows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Workflow limit reached. Upgrade your plan.",
        )

    new_workflow = Workflow(
        tenant_id=tenant_id,
        name=f"{original.name} (Copy)",
        description=original.description,
        definition=copy.deepcopy(original.definition),
        execution_pattern=original.execution_pattern,
        created_by=user_id,
    )
    db.add(new_workflow)
    await db.commit()
    await db.refresh(new_workflow)
    return new_workflow


async def delete_workflow(
    db: AsyncSession, tenant_id: UUID, workflow_id: UUID
) -> None:
    """Soft-delete a workflow (set is_active=False)."""
    workflow = await get_workflow(db, tenant_id, workflow_id)

    # TODO M4: check for running executions -> 409

    workflow.is_active = False
    await db.commit()
