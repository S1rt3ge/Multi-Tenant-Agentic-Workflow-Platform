from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.auth import (
    RegisterRequest,
    RegisterResponse,
    LoginRequest,
    LoginResponse,
    RefreshRequest,
    TokenResponse,
    UpdateProfileRequest,
    UserWithTenantResponse,
    PasswordSetResponse,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(data: RegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register new user and create tenant."""
    result = await auth_service.register(
        db=db,
        email=data.email,
        password=data.password,
        full_name=data.full_name,
        tenant_name=data.tenant_name,
    )
    return result


@router.post("/login", response_model=LoginResponse)
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Authenticate user and return tokens."""
    result = await auth_service.login(db=db, email=data.email, password=data.password)
    return result


@router.post("/refresh", response_model=TokenResponse)
async def refresh(data: RefreshRequest, db: AsyncSession = Depends(get_db)):
    """Refresh access token using refresh token."""
    result = await auth_service.refresh_tokens(
        db=db, refresh_token_str=data.refresh_token
    )
    return result


@router.get("/me", response_model=UserWithTenantResponse)
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get current user profile with tenant info."""
    user = await auth_service.get_profile(db=db, user_id=current_user.id)
    return user


@router.put("/me", response_model=UserWithTenantResponse)
async def update_me(
    data: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update current user profile."""
    user = await auth_service.update_profile(
        db=db,
        user_id=current_user.id,
        full_name=data.full_name,
        password=data.password,
        current_password=data.current_password,
    )
    return user


@router.post("/set-password", response_model=PasswordSetResponse)
async def set_password(
    data: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set password for invited users or rotate password with current secret."""
    if not data.password:
        from fastapi import HTTPException

        raise HTTPException(status_code=400, detail="New password is required")

    result = await auth_service.set_password(
        db=db,
        user_id=current_user.id,
        password=data.password,
        current_password=data.current_password,
    )
    return result
