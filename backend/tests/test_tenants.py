"""Tests for /api/v1/tenants/* endpoints and RBAC edge cases."""

import uuid
import pytest
from httpx import AsyncClient


class TestListUsers:
    """GET /api/v1/tenants/users"""

    async def test_list_users_as_owner(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/tenants/users", headers=auth_headers)
        assert resp.status_code == 200
        users = resp.json()
        assert isinstance(users, list)
        assert len(users) == 1
        assert users[0]["email"] == "owner@test.com"
        assert users[0]["role"] == "owner"

    async def test_list_users_after_invite(self, client: AsyncClient, owner_and_editor):
        resp = await client.get(
            "/api/v1/tenants/users",
            headers=owner_and_editor["owner_headers"],
        )
        assert resp.status_code == 200
        users = resp.json()
        assert len(users) == 2
        emails = {u["email"] for u in users}
        assert "owner@test.com" in emails
        assert "editor@test.com" in emails

    async def test_list_users_no_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/tenants/users")
        assert resp.status_code == 403

    async def test_list_users_as_editor_forbidden(self, client: AsyncClient, owner_and_editor):
        from app.core.security import create_access_token

        editor = owner_and_editor["editor"]
        editor_token = create_access_token(
            user_id=uuid.UUID(editor["id"]),
            tenant_id=uuid.UUID(editor["tenant_id"]),
            role="editor",
        )
        editor_headers = {"Authorization": f"Bearer {editor_token}"}

        resp = await client.get("/api/v1/tenants/users", headers=editor_headers)
        assert resp.status_code == 403


class TestInviteUser:
    """POST /api/v1/tenants/invite"""

    async def test_invite_editor(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/tenants/invite",
            json={"email": "newedit@test.com", "role": "editor"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["email"] == "newedit@test.com"
        assert data["role"] == "editor"
        assert data["is_active"] is True

    async def test_invite_viewer(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/tenants/invite",
            json={"email": "viewer@test.com", "role": "viewer"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["role"] == "viewer"

    async def test_invite_duplicate_email_same_tenant(
        self, client: AsyncClient, auth_headers
    ):
        """Inviting an already-existing email in the same tenant -> 409."""
        await client.post(
            "/api/v1/tenants/invite",
            json={"email": "dup@test.com", "role": "editor"},
            headers=auth_headers,
        )
        resp = await client.post(
            "/api/v1/tenants/invite",
            json={"email": "dup@test.com", "role": "viewer"},
            headers=auth_headers,
        )
        assert resp.status_code == 409
        assert "already in this tenant" in resp.json()["detail"].lower()

    async def test_invite_email_in_other_tenant(self, client: AsyncClient):
        """Email belonging to another tenant -> 409."""
        # Register first tenant
        resp1 = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "user1@test.com",
                "password": "pass123456",
                "full_name": "User One",
                "tenant_name": "Tenant A",
            },
        )
        assert resp1.status_code == 201

        # Register second tenant
        resp2 = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "user2@test.com",
                "password": "pass123456",
                "full_name": "User Two",
                "tenant_name": "Tenant B",
            },
        )
        assert resp2.status_code == 201
        headers2 = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

        # Tenant B owner tries to invite user1 who belongs to Tenant A
        invite_resp = await client.post(
            "/api/v1/tenants/invite",
            json={"email": "user1@test.com", "role": "editor"},
            headers=headers2,
        )
        assert invite_resp.status_code == 409
        assert "another tenant" in invite_resp.json()["detail"].lower()

    async def test_invite_invalid_role(self, client: AsyncClient, auth_headers):
        """Role must match pattern ^(editor|viewer)$ — 'owner' or 'admin' rejected."""
        resp = await client.post(
            "/api/v1/tenants/invite",
            json={"email": "bad@test.com", "role": "owner"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_invite_as_non_owner_forbidden(self, client: AsyncClient):
        """Non-owner (editor) cannot invite users -> 403."""
        # Register and invite an editor
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "bossowner@test.com",
                "password": "pass123456",
                "full_name": "Boss",
                "tenant_name": "Boss Corp",
            },
        )
        owner_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        # Invite editor
        invite = await client.post(
            "/api/v1/tenants/invite",
            json={"email": "loweditor@test.com", "role": "editor"},
            headers=owner_headers,
        )
        assert invite.status_code == 201

        # Login as editor — but the invited user has a temp password we don't know.
        # We'll use a workaround: create access token via DB.
        # Instead, let's verify via the RBAC mechanism by constructing a token.
        from app.core.security import create_access_token

        editor_data = invite.json()
        editor_token = create_access_token(
            user_id=uuid.UUID(editor_data["id"]),
            tenant_id=uuid.UUID(editor_data["tenant_id"]),
            role="editor",
        )
        editor_headers = {"Authorization": f"Bearer {editor_token}"}

        resp = await client.post(
            "/api/v1/tenants/invite",
            json={"email": "another@test.com", "role": "viewer"},
            headers=editor_headers,
        )
        assert resp.status_code == 403


class TestUpdateUserRole:
    """PUT /api/v1/tenants/users/{user_id}/role"""

    async def test_update_role_success(self, client: AsyncClient, owner_and_editor):
        editor_id = owner_and_editor["editor"]["id"]
        resp = await client.put(
            f"/api/v1/tenants/users/{editor_id}/role",
            json={"role": "viewer"},
            headers=owner_and_editor["owner_headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "viewer"

    async def test_update_role_to_owner(self, client: AsyncClient, owner_and_editor):
        """Changing a user to owner role should work."""
        editor_id = owner_and_editor["editor"]["id"]
        resp = await client.put(
            f"/api/v1/tenants/users/{editor_id}/role",
            json={"role": "owner"},
            headers=owner_and_editor["owner_headers"],
        )
        assert resp.status_code == 200
        assert resp.json()["role"] == "owner"

    async def test_owner_cannot_change_own_role(
        self, client: AsyncClient, registered_user, auth_headers
    ):
        """Owner cannot change their own role -> 400."""
        owner_id = registered_user["user_id"]
        resp = await client.put(
            f"/api/v1/tenants/users/{owner_id}/role",
            json={"role": "editor"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "own role" in resp.json()["detail"].lower()

    async def test_update_role_user_not_found(self, client: AsyncClient, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = await client.put(
            f"/api/v1/tenants/users/{fake_id}/role",
            json={"role": "viewer"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_update_role_invalid_role_value(
        self, client: AsyncClient, owner_and_editor
    ):
        editor_id = owner_and_editor["editor"]["id"]
        resp = await client.put(
            f"/api/v1/tenants/users/{editor_id}/role",
            json={"role": "superadmin"},
            headers=owner_and_editor["owner_headers"],
        )
        assert resp.status_code == 422


class TestRemoveUser:
    """DELETE /api/v1/tenants/users/{user_id}"""

    async def test_remove_user_success(self, client: AsyncClient, owner_and_editor):
        editor_id = owner_and_editor["editor"]["id"]
        resp = await client.delete(
            f"/api/v1/tenants/users/{editor_id}",
            headers=owner_and_editor["owner_headers"],
        )
        assert resp.status_code == 204

        # Verify user is gone
        list_resp = await client.get(
            "/api/v1/tenants/users",
            headers=owner_and_editor["owner_headers"],
        )
        assert len(list_resp.json()) == 1

    async def test_owner_cannot_remove_self(
        self, client: AsyncClient, registered_user, auth_headers
    ):
        """Owner cannot delete themselves -> 400."""
        owner_id = registered_user["user_id"]
        resp = await client.delete(
            f"/api/v1/tenants/users/{owner_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "yourself" in resp.json()["detail"].lower()

    async def test_remove_nonexistent_user(self, client: AsyncClient, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = await client.delete(
            f"/api/v1/tenants/users/{fake_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_remove_user_as_editor_forbidden(self, client: AsyncClient):
        """Editor cannot remove users -> 403."""
        reg = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "rmowner@test.com",
                "password": "pass123456",
                "full_name": "RM Owner",
                "tenant_name": "RM Corp",
            },
        )
        owner_headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

        # Invite editor
        invite = await client.post(
            "/api/v1/tenants/invite",
            json={"email": "rmeditor@test.com", "role": "editor"},
            headers=owner_headers,
        )
        editor_data = invite.json()

        # Create token for editor
        from app.core.security import create_access_token

        editor_token = create_access_token(
            user_id=uuid.UUID(editor_data["id"]),
            tenant_id=uuid.UUID(editor_data["tenant_id"]),
            role="editor",
        )
        editor_headers = {"Authorization": f"Bearer {editor_token}"}

        # Invite a viewer to have someone to try removing
        viewer = await client.post(
            "/api/v1/tenants/invite",
            json={"email": "rmviewer@test.com", "role": "viewer"},
            headers=owner_headers,
        )
        viewer_id = viewer.json()["id"]

        # Editor tries to delete viewer -> 403
        resp = await client.delete(
            f"/api/v1/tenants/users/{viewer_id}",
            headers=editor_headers,
        )
        assert resp.status_code == 403


class TestTenantIsolation:
    """Cross-tenant isolation: users from tenant A cannot see/modify tenant B."""

    async def test_cross_tenant_user_list_isolation(self, client: AsyncClient):
        """Each tenant only sees their own users."""
        # Register tenant A
        reg_a = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "a@test.com",
                "password": "pass123456",
                "full_name": "A User",
                "tenant_name": "Tenant A",
            },
        )
        headers_a = {"Authorization": f"Bearer {reg_a.json()['access_token']}"}

        # Register tenant B
        reg_b = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "b@test.com",
                "password": "pass123456",
                "full_name": "B User",
                "tenant_name": "Tenant B",
            },
        )
        headers_b = {"Authorization": f"Bearer {reg_b.json()['access_token']}"}

        # Tenant A lists their users -> only sees themselves
        users_a = await client.get("/api/v1/tenants/users", headers=headers_a)
        assert len(users_a.json()) == 1
        assert users_a.json()[0]["email"] == "a@test.com"

        # Tenant B lists their users -> only sees themselves
        users_b = await client.get("/api/v1/tenants/users", headers=headers_b)
        assert len(users_b.json()) == 1
        assert users_b.json()[0]["email"] == "b@test.com"
