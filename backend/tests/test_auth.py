"""Tests for /api/v1/auth/* endpoints."""

import uuid

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

    async def test_register_duplicate_email_case_insensitive(self, client: AsyncClient):
        first = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "Case@Test.com",
                "password": "password123",
                "full_name": "Case User",
                "tenant_name": "Case Tenant",
            },
        )
        assert first.status_code == 201

        second = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "case@test.com",
                "password": "password123",
                "full_name": "Case User Two",
                "tenant_name": "Case Tenant Two",
            },
        )
        assert second.status_code == 409

    async def test_register_normalizes_email_to_lowercase(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "Trim.Case@Test.com ",
                "password": "password123",
                "full_name": "Normalize User",
                "tenant_name": "Normalize Tenant",
            },
        )
        assert resp.status_code == 201

        headers = {"Authorization": f"Bearer {resp.json()['access_token']}"}
        me = await client.get("/api/v1/auth/me", headers=headers)
        assert me.status_code == 200
        assert me.json()["email"] == "trim.case@test.com"

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

    async def test_login_case_insensitive_email(self, client: AsyncClient):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "MixedCase@Test.com",
                "password": "password123",
                "full_name": "Mixed User",
                "tenant_name": "Mixed Tenant",
            },
        )
        assert reg.status_code == 201

        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "mixedcase@test.com", "password": "password123"},
        )
        assert login.status_code == 200

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

    async def test_login_blocked_when_password_reset_required(self, client: AsyncClient):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "owner-reset@test.com",
                "password": "password123",
                "full_name": "Owner Reset",
                "tenant_name": "Reset Tenant",
            },
        )
        assert reg.status_code == 201
        owner_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        invite = await client.post(
            "/api/v1/tenants/invite",
            json={"email": "invitee-reset@test.com", "role": "editor"},
            headers=owner_headers,
        )
        assert invite.status_code == 201
        temp_password = invite.json()["temporary_password"]

        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "invitee-reset@test.com", "password": temp_password},
        )
        assert login.status_code == 403
        assert "password reset required" in login.json()["detail"].lower()


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
        from app.core.security import create_access_token

        fresh_token = create_access_token(
            user_id=uuid.UUID(registered_user["user_id"]),
            tenant_id=uuid.UUID(registered_user["tenant_id"]),
            role="owner",
        )
        fresh_headers = {"Authorization": f"Bearer {fresh_token}"}

        resp = await client.put(
            "/api/v1/auth/me",
            json={"password": "newpassword456", "current_password": "password123"},
            headers=fresh_headers,
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
        from app.core.security import create_access_token

        me_resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert me_resp.status_code == 200
        me = me_resp.json()

        fresh_token = create_access_token(
            user_id=uuid.UUID(me["id"]),
            tenant_id=uuid.UUID(me["tenant"]["id"]),
            role=me["role"],
        )
        fresh_headers = {"Authorization": f"Bearer {fresh_token}"}

        resp = await client.put(
            "/api/v1/auth/me",
            json={
                "full_name": "Both Updated",
                "password": "bothpass789",
                "current_password": "password123",
            },
            headers=fresh_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["full_name"] == "Both Updated"

    async def test_update_password_requires_current_password(self, client: AsyncClient, auth_headers):
        resp = await client.put(
            "/api/v1/auth/me",
            json={"password": "newpassword456"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "current password" in resp.json()["detail"].lower()

    async def test_set_password_for_invited_user(self, client: AsyncClient):
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "owner-setpass@test.com",
                "password": "password123",
                "full_name": "Owner",
                "tenant_name": "Owner Tenant",
            },
        )
        assert reg.status_code == 201
        owner_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        invite = await client.post(
            "/api/v1/tenants/invite",
            json={"email": "invitee-setpass@test.com", "role": "viewer"},
            headers=owner_headers,
        )
        assert invite.status_code == 201
        temp_password = invite.json()["temporary_password"]

        blocked_login = await client.post(
            "/api/v1/auth/login",
            json={"email": "invitee-setpass@test.com", "password": temp_password},
        )
        assert blocked_login.status_code == 403

        from app.core.security import create_access_token
        import uuid

        invited_user = invite.json()
        invited_token = create_access_token(
            user_id=uuid.UUID(invited_user["id"]),
            tenant_id=uuid.UUID(invited_user["tenant_id"]),
            role=invited_user["role"],
        )
        invited_headers = {"Authorization": f"Bearer {invited_token}"}

        set_pass = await client.post(
            "/api/v1/auth/set-password",
            json={"password": "newsecure123"},
            headers=invited_headers,
        )
        assert set_pass.status_code == 200
        assert set_pass.json()["must_change_password"] is False

        login = await client.post(
            "/api/v1/auth/login",
            json={"email": "invitee-setpass@test.com", "password": "newsecure123"},
        )
        assert login.status_code == 200

    async def test_update_me_no_auth(self, client: AsyncClient):
        resp = await client.put("/api/v1/auth/me", json={"full_name": "Hacker"})
        assert resp.status_code == 403
