"""Tests for /api/v1/auth/* endpoints."""

import pytest
from httpx import AsyncClient


class TestRegister:
    """POST /api/v1/auth/register"""

    async def test_register_success(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "new@test.com",
                "password": "password123",
                "full_name": "New User",
                "tenant_name": "New Tenant",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert "user_id" in data
        assert "tenant_id" in data
        assert "access_token" in data
        assert "refresh_token" in data

    async def test_register_creates_owner_role(self, client: AsyncClient):
        """Registered user should be owner of the new tenant."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "owner2@test.com",
                "password": "password123",
                "full_name": "Owner Two",
                "tenant_name": "Another Corp",
            },
        )
        assert resp.status_code == 201
        data = resp.json()

        # Use returned token to check /me
        headers = {"Authorization": f"Bearer {data['access_token']}"}
        me_resp = await client.get("/api/v1/auth/me", headers=headers)
        assert me_resp.status_code == 200
        assert me_resp.json()["role"] == "owner"

    async def test_register_duplicate_email(self, client: AsyncClient, registered_user):
        """Duplicate email should return 409."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": registered_user["email"],
                "password": "another123",
                "full_name": "Duplicate",
                "tenant_name": "Dup Tenant",
            },
        )
        assert resp.status_code == 409
        assert "already registered" in resp.json()["detail"].lower()

    async def test_register_short_password(self, client: AsyncClient):
        """Password shorter than 6 chars should be rejected (422)."""
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "short@test.com",
                "password": "123",
                "full_name": "Short Pass",
                "tenant_name": "Corp",
            },
        )
        assert resp.status_code == 422

    async def test_register_missing_fields(self, client: AsyncClient):
        """Missing required fields should return 422."""
        resp = await client.post("/api/v1/auth/register", json={"email": "a@b.com"})
        assert resp.status_code == 422


class TestLogin:
    """POST /api/v1/auth/login"""

    async def test_login_success(self, client: AsyncClient, registered_user):
        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": registered_user["email"],
                "password": registered_user["password"],
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert "refresh_token" in data
        assert "user" in data
        assert data["user"]["email"] == registered_user["email"]
        assert data["user"]["role"] == "owner"
        assert "tenant" in data["user"]

    async def test_login_wrong_password(self, client: AsyncClient, registered_user):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": registered_user["email"], "password": "wrongpassword"},
        )
        assert resp.status_code == 401
        assert "invalid" in resp.json()["detail"].lower()

    async def test_login_nonexistent_email(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "ghost@test.com", "password": "anything"},
        )
        assert resp.status_code == 401

    async def test_login_deactivated_user(
        self, client: AsyncClient, registered_user, db_session
    ):
        """Deactivated user cannot login."""
        from sqlalchemy import update
        from app.models.user import User
        from uuid import UUID

        await db_session.execute(
            update(User)
            .where(User.id == UUID(registered_user["user_id"]))
            .values(is_active=False)
        )
        await db_session.commit()

        resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": registered_user["email"],
                "password": registered_user["password"],
            },
        )
        assert resp.status_code == 401
        assert "deactivated" in resp.json()["detail"].lower()


class TestRefresh:
    """POST /api/v1/auth/refresh"""

    async def test_refresh_success(self, client: AsyncClient, registered_user):
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": registered_user["refresh_token"]},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data

    async def test_refresh_invalid_token(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": "invalid.token.here"},
        )
        assert resp.status_code == 401

    async def test_refresh_with_access_token_fails(
        self, client: AsyncClient, registered_user
    ):
        """Using an access_token as refresh should fail (type mismatch)."""
        resp = await client.post(
            "/api/v1/auth/refresh",
            json={"refresh_token": registered_user["access_token"]},
        )
        assert resp.status_code == 401


class TestGetMe:
    """GET /api/v1/auth/me"""

    async def test_get_me_success(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "owner@test.com"
        assert data["full_name"] == "Test Owner"
        assert data["role"] == "owner"
        assert "tenant" in data
        assert data["tenant"]["name"] == "Test Corp"

    async def test_get_me_no_token(self, client: AsyncClient):
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 403  # HTTPBearer returns 403 when no creds

    async def test_get_me_invalid_token(self, client: AsyncClient):
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid.jwt.token"},
        )
        assert resp.status_code == 401


class TestUpdateMe:
    """PUT /api/v1/auth/me"""

    async def test_update_name(self, client: AsyncClient, auth_headers):
        resp = await client.put(
            "/api/v1/auth/me",
            json={"full_name": "Updated Name"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Updated Name"

    async def test_update_password(
        self, client: AsyncClient, registered_user, auth_headers
    ):
        """Update password, then login with new password."""
        resp = await client.put(
            "/api/v1/auth/me",
            json={"password": "newpassword456"},
            headers=auth_headers,
        )
        assert resp.status_code == 200

        # Login with new password
        login_resp = await client.post(
            "/api/v1/auth/login",
            json={
                "email": registered_user["email"],
                "password": "newpassword456",
            },
        )
        assert login_resp.status_code == 200

        # Old password should fail
        old_login = await client.post(
            "/api/v1/auth/login",
            json={
                "email": registered_user["email"],
                "password": registered_user["password"],
            },
        )
        assert old_login.status_code == 401

    async def test_update_both_fields(self, client: AsyncClient, auth_headers):
        resp = await client.put(
            "/api/v1/auth/me",
            json={"full_name": "Both Updated", "password": "bothpass789"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Both Updated"

    async def test_update_me_no_auth(self, client: AsyncClient):
        resp = await client.put("/api/v1/auth/me", json={"full_name": "Hacker"})
        assert resp.status_code == 403
