from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_tenant, require_role
from app.models.user import User
from app.schemas.agent_config import (
    AgentConfigCreate,
    AgentConfigUpdate,
    AgentConfigResponse,
)
from app.services import agent_service

router = APIRouter(prefix="/workflows/{wf_id}/agents", tags=["agents"])


@router.get("/", response_model=list[AgentConfigResponse])
async def list_agents(
    wf_id: UUID,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """List all agent configs for a workflow."""
    agents = await agent_service.list_agents(db=db, tenant_id=tenant_id, workflow_id=wf_id)
    return agents


@router.post("/", response_model=AgentConfigResponse, status_code=201)
async def create_agent(
    wf_id: UUID,
    data: AgentConfigCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "editor")),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """Create an agent config for a workflow node."""
    agent = await agent_service.create_agent(
        db=db,
        tenant_id=tenant_id,
        workflow_id=wf_id,
        node_id=data.node_id,
        name=data.name,
        role=data.role,
        system_prompt=data.system_prompt,
        model=data.model,
        tools=data.tools,
        memory_type=data.memory_type,
        max_tokens=data.max_tokens,
        temperature=data.temperature,
    )
    return agent


@router.put("/{agent_id}", response_model=AgentConfigResponse)
async def update_agent(
    wf_id: UUID,
    agent_id: UUID,
    data: AgentConfigUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "editor")),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """Update an agent config. Partial update."""
    agent = await agent_service.update_agent(
        db=db,
        tenant_id=tenant_id,
        workflow_id=wf_id,
        agent_id=agent_id,
        name=data.name,
        role=data.role,
        system_prompt=data.system_prompt,
        model=data.model,
        tools=data.tools,
        memory_type=data.memory_type,
        max_tokens=data.max_tokens,
        temperature=data.temperature,
    )
    return agent


@router.delete("/{agent_id}", status_code=204)
async def delete_agent(
    wf_id: UUID,
    agent_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "editor")),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """Delete an agent config."""
    await agent_service.delete_agent(
        db=db, tenant_id=tenant_id, workflow_id=wf_id, agent_id=agent_id
    )
