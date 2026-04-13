from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_tenant, require_role
from app.models.user import User
from app.schemas.auth import (
    InviteUserRequest,
    UpdateRoleRequest,
    UserResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/tenants", tags=["tenants"])


@router.get("/users", response_model=list[UserResponse])
async def list_users(
    tenant_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
):
    """List all users in current tenant."""
    users = await auth_service.list_tenant_users(db=db, tenant_id=tenant_id)
    return users


@router.post("/invite", response_model=UserResponse, status_code=201)
async def invite_user(
    data: InviteUserRequest,
    tenant_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner")),
):
    """Invite a new user to the tenant. Only owner can invite."""
    user = await auth_service.invite_user(
        db=db,
        tenant_id=tenant_id,
        email=data.email,
        role=data.role,
    )
    return user


@router.put("/users/{user_id}/role", response_model=UserResponse)
async def update_user_role(
    user_id: UUID,
    data: UpdateRoleRequest,
    tenant_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner")),
):
    """Update a user's role. Only owner can change roles."""
    user = await auth_service.update_user_role(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        new_role=data.role,
        current_user_id=current_user.id,
    )
    return user


@router.delete("/users/{user_id}", status_code=204)
async def remove_user(
    user_id: UUID,
    tenant_id: UUID = Depends(get_current_tenant),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner")),
):
    """Remove a user from the tenant. Only owner can remove."""
    await auth_service.remove_user(
        db=db,
        tenant_id=tenant_id,
        user_id=user_id,
        current_user_id=current_user.id,
    )
