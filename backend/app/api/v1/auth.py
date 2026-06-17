from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
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


def _cookie_secure(settings) -> bool:
    if settings.REFRESH_COOKIE_SECURE is not None:
        return settings.REFRESH_COOKIE_SECURE
    return settings.is_production


def _set_refresh_cookie(response: Response, token: str) -> None:
    """Store the refresh token in an httpOnly cookie (not readable by JS)."""
    settings = get_settings()
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=token,
        max_age=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=_cookie_secure(settings),
        samesite=settings.REFRESH_COOKIE_SAMESITE,
        path=settings.REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    settings = get_settings()
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        httponly=True,
        secure=_cookie_secure(settings),
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(
    data: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Register new user and create tenant."""
    result = await auth_service.register(
        db=db,
        email=data.email,
        password=data.password,
        full_name=data.full_name,
        tenant_name=data.tenant_name,
    )
    _set_refresh_cookie(response, result["refresh_token"])
    return result


@router.post("/login", response_model=LoginResponse)
async def login(
    data: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate user and return tokens."""
    result = await auth_service.login(db=db, email=data.email, password=data.password)
    _set_refresh_cookie(response, result["refresh_token"])
    return result


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    response: Response,
    data: RefreshRequest | None = None,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Refresh access token. Token comes from the httpOnly cookie by default;
    an explicit request body value takes precedence for compatibility."""
    body_token = data.refresh_token if data else None
    token = body_token or refresh_token
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token is required")
    result = await auth_service.refresh_tokens(db=db, refresh_token_str=token)
    _set_refresh_cookie(response, result["refresh_token"])
    return result


@router.post("/logout", status_code=204)
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: AsyncSession = Depends(get_db),
):
    """Revoke the presented refresh token and clear the cookie."""
    if refresh_token:
        await auth_service.revoke_refresh_token(db=db, refresh_token_str=refresh_token)
    _clear_refresh_cookie(response)
    # Returning None with status_code=204 keeps the Set-Cookie deletion header.
    return None


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
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Set password for invited users or rotate password with current secret."""
    if not data.password:
        raise HTTPException(status_code=400, detail="New password is required")

    result = await auth_service.set_password(
        db=db,
        user_id=current_user.id,
        password=data.password,
        current_password=data.current_password,
    )
    if isinstance(result, dict) and result.get("refresh_token"):
        _set_refresh_cookie(response, result["refresh_token"])
    return result
