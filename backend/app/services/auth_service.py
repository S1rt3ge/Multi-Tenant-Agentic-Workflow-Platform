import re
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.models.tenant import Tenant
from app.models.user import User


def _slugify(name: str) -> str:
    """Convert tenant name to URL-friendly slug."""
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s-]+", "-", slug)
    return slug


async def register(
    db: AsyncSession, email: str, password: str, full_name: str, tenant_name: str
) -> dict:
    """Register a new user + create tenant. User becomes owner."""
    # Check duplicate email
    existing = await db.execute(select(User).where(User.email == email))
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Email already registered"
        )

    # Create tenant
    slug = _slugify(tenant_name)
    # Ensure slug uniqueness
    existing_tenant = await db.execute(select(Tenant).where(Tenant.slug == slug))
    if existing_tenant.scalar_one_or_none():
        import uuid as _uuid

        slug = f"{_slugify(tenant_name)}-{str(_uuid.uuid4())[:8]}"

    tenant = Tenant(name=tenant_name, slug=slug)
    db.add(tenant)
    await db.flush()

    # Create user as owner
    user = User(
        tenant_id=tenant.id,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        role="owner",
    )
    db.add(user)
    await db.flush()

    # Generate tokens
    access_token = create_access_token(user.id, tenant.id, user.role)
    refresh_token = create_refresh_token(user.id, tenant.id)

    await db.commit()

    return {
        "user_id": user.id,
        "tenant_id": tenant.id,
        "access_token": access_token,
        "refresh_token": refresh_token,
    }


async def login(db: AsyncSession, email: str, password: str) -> dict:
    """Authenticate user and return tokens + user with tenant."""
    result = await db.execute(
        select(User).options(selectinload(User.tenant)).where(User.email == email)
    )
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Account is deactivated",
        )

    access_token = create_access_token(user.id, user.tenant_id, user.role)
    refresh_token = create_refresh_token(user.id, user.tenant_id)

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": user,
    }


async def get_profile(db: AsyncSession, user_id: UUID) -> User:
    """Get user profile with tenant info."""
    result = await db.execute(
        select(User).options(selectinload(User.tenant)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


async def refresh_tokens(db: AsyncSession, refresh_token_str: str) -> dict:
    """Validate refresh token and return a new access token."""
    payload = decode_token(refresh_token_str)
    if payload is None or payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        )

    user_id = payload.get("sub")
    tenant_id = payload.get("tenant_id")
    if user_id is None or tenant_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Verify user still exists and is active
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or deactivated",
        )

    access_token = create_access_token(user.id, user.tenant_id, user.role)
    return {"access_token": access_token}


async def update_profile(
    db: AsyncSession, user_id: UUID, full_name: str | None, password: str | None
) -> User:
    """Update user profile (name and/or password)."""
    result = await db.execute(
        select(User).options(selectinload(User.tenant)).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if full_name is not None:
        user.full_name = full_name
    if password is not None:
        user.password_hash = hash_password(password)

    await db.commit()

    # Re-fetch with tenant loaded (db.refresh would expire relationships)
    result = await db.execute(
        select(User).options(selectinload(User.tenant)).where(User.id == user_id)
    )
    user = result.scalar_one()
    return user


async def list_tenant_users(db: AsyncSession, tenant_id: UUID) -> list[User]:
    """List all users in a tenant."""
    result = await db.execute(
        select(User).where(User.tenant_id == tenant_id).order_by(User.created_at)
    )
    return list(result.scalars().all())


async def invite_user(db: AsyncSession, tenant_id: UUID, email: str, role: str) -> User:
    """Invite a new user to the tenant."""
    # Check if email already exists
    existing = await db.execute(select(User).where(User.email == email))
    existing_user = existing.scalar_one_or_none()
    if existing_user:
        if existing_user.tenant_id == tenant_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already in this tenant",
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="User already belongs to another tenant",
            )

    # Create user with temporary password
    import uuid as _uuid

    temp_password = str(_uuid.uuid4())[:12]
    user = User(
        tenant_id=tenant_id,
        email=email,
        password_hash=hash_password(temp_password),
        role=role,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def update_user_role(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    new_role: str,
    current_user_id: UUID,
) -> User:
    """Update a user's role within the tenant."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Owner cannot change their own role
    if user.id == current_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot change your own role",
        )

    user.role = new_role
    await db.commit()
    await db.refresh(user)
    return user


async def remove_user(
    db: AsyncSession, tenant_id: UUID, user_id: UUID, current_user_id: UUID
) -> None:
    """Remove a user from the tenant."""
    result = await db.execute(
        select(User).where(User.id == user_id, User.tenant_id == tenant_id)
    )
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # Owner cannot delete themselves
    if user.id == current_user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot remove yourself"
        )

    await db.delete(user)
    await db.commit()
