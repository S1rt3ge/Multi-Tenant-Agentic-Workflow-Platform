from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.agent_config import AgentConfig
from app.models.workflow import Workflow
from app.models.tenant import Tenant
from app.schemas.agent_config import VALID_ROLES, VALID_MODELS, VALID_MEMORY_TYPES


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_workflow(db: AsyncSession, tenant_id: UUID, workflow_id: UUID) -> Workflow:
    """Get a workflow ensuring it belongs to the tenant and is active."""
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


def _validate_fields(role: str | None, model: str | None, memory_type: str | None) -> None:
    """Validate enum-like fields."""
    if role is not None and role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{role}'. Must be one of: {', '.join(sorted(VALID_ROLES))}",
        )
    if model is not None and model not in VALID_MODELS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model '{model}'. Must be one of: {', '.join(sorted(VALID_MODELS))}",
        )
    if memory_type is not None and memory_type not in VALID_MEMORY_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid memory_type '{memory_type}'. Must be one of: {', '.join(sorted(VALID_MEMORY_TYPES))}",
        )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def list_agents(
    db: AsyncSession, tenant_id: UUID, workflow_id: UUID
) -> list[AgentConfig]:
    """List all agent configs for a workflow."""
    await _get_workflow(db, tenant_id, workflow_id)

    result = await db.execute(
        select(AgentConfig)
        .where(
            AgentConfig.workflow_id == workflow_id,
            AgentConfig.tenant_id == tenant_id,
        )
        .order_by(AgentConfig.created_at)
    )
    return list(result.scalars().all())


async def create_agent(
    db: AsyncSession,
    tenant_id: UUID,
    workflow_id: UUID,
    node_id: str,
    name: str,
    role: str,
    system_prompt: str,
    model: str,
    tools: list,
    memory_type: str,
    max_tokens: int,
    temperature: float,
) -> AgentConfig:
    """Create an agent config after validations."""
    wf = await _get_workflow(db, tenant_id, workflow_id)
    _validate_fields(role, model, memory_type)

    # Check max agents per workflow limit
    tenant_result = await db.execute(
        select(Tenant).where(Tenant.id == tenant_id).with_for_update()
    )
    tenant = tenant_result.scalar_one_or_none()
    if tenant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tenant not found")

    count_result = await db.execute(
        select(sa_func.count(AgentConfig.id)).where(
            AgentConfig.workflow_id == workflow_id,
            AgentConfig.tenant_id == tenant_id,
        )
    )
    current_count = count_result.scalar() or 0

    if current_count >= tenant.max_agents_per_workflow:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Agent limit reached ({tenant.max_agents_per_workflow} per workflow)",
        )

    # Check unique node_id within workflow
    existing = await db.execute(
        select(AgentConfig).where(
            AgentConfig.workflow_id == workflow_id,
            AgentConfig.node_id == node_id,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Agent config for node '{node_id}' already exists in this workflow",
        )

    agent = AgentConfig(
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        node_id=node_id,
        name=name,
        role=role,
        system_prompt=system_prompt,
        model=model,
        tools=tools,
        memory_type=memory_type,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


async def update_agent(
    db: AsyncSession,
    tenant_id: UUID,
    workflow_id: UUID,
    agent_id: UUID,
    name: str | None = None,
    role: str | None = None,
    system_prompt: str | None = None,
    model: str | None = None,
    tools: list | None = None,
    memory_type: str | None = None,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> AgentConfig:
    """Update an agent config. Partial update."""
    await _get_workflow(db, tenant_id, workflow_id)
    _validate_fields(role, model, memory_type)

    result = await db.execute(
        select(AgentConfig).where(
            AgentConfig.id == agent_id,
            AgentConfig.workflow_id == workflow_id,
            AgentConfig.tenant_id == tenant_id,
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent config not found")

    if name is not None:
        agent.name = name
    if role is not None:
        agent.role = role
    if system_prompt is not None:
        agent.system_prompt = system_prompt
    if model is not None:
        agent.model = model
    if tools is not None:
        agent.tools = tools
    if memory_type is not None:
        agent.memory_type = memory_type
    if max_tokens is not None:
        agent.max_tokens = max_tokens
    if temperature is not None:
        agent.temperature = temperature

    await db.commit()
    await db.refresh(agent)
    return agent


async def delete_agent(
    db: AsyncSession, tenant_id: UUID, workflow_id: UUID, agent_id: UUID
) -> None:
    """Delete an agent config."""
    await _get_workflow(db, tenant_id, workflow_id)

    result = await db.execute(
        select(AgentConfig).where(
            AgentConfig.id == agent_id,
            AgentConfig.workflow_id == workflow_id,
            AgentConfig.tenant_id == tenant_id,
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Agent config not found")

    await db.delete(agent)
    await db.commit()
