from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_tenant, require_role
from app.models.user import User
from app.schemas.tool import (
    ToolCreate,
    ToolUpdate,
    ToolTestInput,
    ToolResponse,
    ToolTestResponse,
)
from app.services import tool_service

router = APIRouter(prefix="/tools", tags=["tools"])


@router.post("/", response_model=ToolResponse, status_code=201)
async def create_tool(
    data: ToolCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "editor")),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """Register a new tool. Viewers cannot create."""
    tool = await tool_service.create_tool(
        db=db,
        tenant_id=tenant_id,
        name=data.name,
        description=data.description,
        tool_type=data.tool_type,
        config=data.config,
    )
    return tool


@router.get("/", response_model=list[ToolResponse])
async def list_tools(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """List all active tools for the current tenant."""
    tools = await tool_service.list_tools(db=db, tenant_id=tenant_id)
    return tools


@router.put("/{tool_id}", response_model=ToolResponse)
async def update_tool(
    tool_id: UUID,
    data: ToolUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "editor")),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """Update a tool. Viewers cannot update."""
    tool = await tool_service.update_tool(
        db=db,
        tenant_id=tenant_id,
        tool_id=tool_id,
        name=data.name,
        description=data.description,
        tool_type=data.tool_type,
        config=data.config,
    )
    return tool


@router.delete("/{tool_id}", status_code=204)
async def delete_tool(
    tool_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "editor")),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """Soft-delete a tool. Viewers cannot delete."""
    await tool_service.delete_tool(db=db, tenant_id=tenant_id, tool_id=tool_id)


@router.post("/{tool_id}/test", response_model=ToolTestResponse)
async def test_tool(
    tool_id: UUID,
    data: ToolTestInput = ToolTestInput(),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """Test a tool by executing a sample request."""
    result = await tool_service.test_tool(
        db=db, tenant_id=tenant_id, tool_id=tool_id, test_input=data.test_input
    )
    return result
