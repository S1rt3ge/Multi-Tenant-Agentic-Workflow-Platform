from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


# --- Request schemas ---


class RegisterRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    password: str = Field(..., min_length=6, max_length=128)
    full_name: str = Field(..., min_length=1, max_length=255)
    tenant_name: str = Field(..., min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class UpdateProfileRequest(BaseModel):
    full_name: str | None = None
    password: str | None = Field(None, min_length=6, max_length=128)


class InviteUserRequest(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    role: str = Field(..., pattern="^(editor|viewer)$")


class UpdateRoleRequest(BaseModel):
    role: str = Field(..., pattern="^(owner|editor|viewer)$")


# --- Response schemas ---


class TenantResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    plan: str
    max_workflows: int
    max_agents_per_workflow: int
    monthly_token_budget: int
    tokens_used_this_month: int

    model_config = {"from_attributes": True}


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    role: str
    is_active: bool
    tenant_id: UUID
    created_at: datetime

    model_config = {"from_attributes": True}


class UserWithTenantResponse(BaseModel):
    id: UUID
    email: str
    full_name: str | None
    role: str
    is_active: bool
    tenant: TenantResponse

    model_config = {"from_attributes": True}


class RegisterResponse(BaseModel):
    user_id: UUID
    tenant_id: UUID
    access_token: str
    refresh_token: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: UserWithTenantResponse


class TokenResponse(BaseModel):
    access_token: str
