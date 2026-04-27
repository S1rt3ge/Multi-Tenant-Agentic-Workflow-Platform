"""Tests for /api/v1/tools/* endpoints (M5 — Tool Registry)."""

import uuid

import pytest
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helper: create a tool via API
# ---------------------------------------------------------------------------

API_TOOL_CONFIG = {
    "url": "https://api.example.com/data",
    "method": "GET",
    "headers": {"Authorization": "Bearer secret-token-123"},
}

UNSAFE_API_TOOL_CONFIG = {
    "url": "http://127.0.0.1:9999/internal",
    "method": "GET",
    "headers": {"Authorization": "Bearer secret-token-123"},
}

DB_TOOL_CONFIG = {
    "connection_string": "postgresql://user:password123@host:5432/mydb",
    "query_template": "SELECT * FROM table WHERE id = {input}",
}

FS_TOOL_CONFIG = {
    "base_path": "/data/uploads",
    "allowed_extensions": [".csv", ".json"],
}


@pytest.fixture(autouse=True)
def mock_public_api_dns():
    """Keep API tool CRUD tests deterministic without weakening URL checks."""
    with patch(
        "app.engine.tools.safe_http.resolve_public_addresses",
        return_value={"93.184.216.34"},
    ), patch(
        "app.services.tool_service.resolve_public_addresses",
        return_value={"93.184.216.34"},
    ):
        yield


async def _create_tool(
    client: AsyncClient,
    headers: dict,
    name: str = "Test API Tool",
    tool_type: str = "api",
    config: dict | None = None,
    **overrides,
) -> dict:
    payload = {
        "name": name,
        "description": "A test tool",
        "tool_type": tool_type,
        "config": config or API_TOOL_CONFIG,
        **overrides,
    }
    resp = await client.post("/api/v1/tools/", json=payload, headers=headers)
    assert resp.status_code == 201, f"Create tool failed: {resp.text}"
    return resp.json()


# ===========================================================================
# CREATE
# ===========================================================================


class TestCreateTool:
    """POST /api/v1/tools/"""

    async def test_create_api_tool_success(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/tools/",
            json={
                "name": "Weather API",
                "description": "Fetches weather data",
                "tool_type": "api",
                "config": API_TOOL_CONFIG,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Weather API"
        assert data["description"] == "Fetches weather data"
        assert data["tool_type"] == "api"
        assert data["is_active"] is True
        assert "id" in data
        assert "tenant_id" in data
        # Authorization header should be masked in response
        assert data["config"]["headers"]["Authorization"] == "****"

    async def test_create_database_tool_success(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/tools/",
            json={
                "name": "PG Lookup",
                "description": "Queries customer DB",
                "tool_type": "database",
                "config": DB_TOOL_CONFIG,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["tool_type"] == "database"
        # Password in connection string should be masked
        assert "****" in data["config"]["connection_string"]
        assert "password123" not in data["config"]["connection_string"]

    async def test_create_file_system_tool_success(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/tools/",
            json={
                "name": "File Reader",
                "description": "Reads CSV/JSON files",
                "tool_type": "file_system",
                "config": FS_TOOL_CONFIG,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["tool_type"] == "file_system"
        assert data["config"]["base_path"] == "/data/uploads"

    async def test_create_missing_name(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/tools/",
            json={
                "description": "No name",
                "tool_type": "api",
                "config": API_TOOL_CONFIG,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_create_invalid_tool_type(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/tools/",
            json={
                "name": "Bad Type",
                "tool_type": "magic",
                "config": {"url": "http://x.com"},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_create_api_tool_missing_url(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/tools/",
            json={
                "name": "No URL Tool",
                "tool_type": "api",
                "config": {"method": "GET"},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "url" in resp.json()["detail"].lower()

    async def test_create_api_tool_invalid_url(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/tools/",
            json={
                "name": "Bad URL Tool",
                "tool_type": "api",
                "config": {"url": "not-a-url"},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "invalid url" in resp.json()["detail"].lower()

    async def test_create_api_tool_invalid_method(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/tools/",
            json={
                "name": "Bad Method Tool",
                "tool_type": "api",
                "config": {"url": "https://api.example.com", "method": "PATCH"},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "method" in resp.json()["detail"].lower()

    async def test_create_api_tool_blocks_localhost_url(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/tools/",
            json={
                "name": "Localhost API",
                "tool_type": "api",
                "config": {"url": "http://localhost:8000/internal", "method": "GET"},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400

    async def test_create_api_tool_blocks_private_ip_url(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/tools/",
            json={
                "name": "Private IP API",
                "tool_type": "api",
                "config": {"url": "http://127.0.0.1:9999/internal", "method": "GET"},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400

    async def test_create_api_tool_rejects_http_scheme(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/tools/",
            json={
                "name": "HTTP API Tool",
                "tool_type": "api",
                "config": {"url": "http://api.example.com/data", "method": "GET"},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "https" in resp.json()["detail"].lower()

    async def test_create_api_tool_rejects_embedded_url_credentials(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/tools/",
            json={
                "name": "Credential URL API Tool",
                "tool_type": "api",
                "config": {"url": "https://user:pass@api.example.com/data", "method": "GET"},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "credentials" in resp.json()["detail"].lower()

    async def test_create_database_tool_missing_connection_string(
        self, client: AsyncClient, auth_headers
    ):
        resp = await client.post(
            "/api/v1/tools/",
            json={
                "name": "No Conn DB",
                "tool_type": "database",
                "config": {"query_template": "SELECT 1"},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "connection_string" in resp.json()["detail"].lower()

    async def test_create_file_system_tool_missing_base_path(
        self, client: AsyncClient, auth_headers
    ):
        resp = await client.post(
            "/api/v1/tools/",
            json={
                "name": "No Path FS",
                "tool_type": "file_system",
                "config": {"allowed_extensions": [".csv"]},
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "base_path" in resp.json()["detail"].lower()

    async def test_create_duplicate_name_conflict(self, client: AsyncClient, auth_headers):
        await _create_tool(client, auth_headers, name="Unique Tool")

        resp = await client.post(
            "/api/v1/tools/",
            json={
                "name": "Unique Tool",
                "tool_type": "api",
                "config": API_TOOL_CONFIG,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()

    async def test_create_no_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/tools/",
            json={
                "name": "Unauthorized",
                "tool_type": "api",
                "config": API_TOOL_CONFIG,
            },
        )
        assert resp.status_code == 401

    async def test_create_default_description(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/tools/",
            json={
                "name": "No Desc",
                "tool_type": "api",
                "config": API_TOOL_CONFIG,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["description"] == ""


# ===========================================================================
# LIST
# ===========================================================================


class TestListTools:
    """GET /api/v1/tools/"""

    async def test_list_empty(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/tools/", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_tools(self, client: AsyncClient, auth_headers):
        await _create_tool(client, auth_headers, name="Tool A")
        await _create_tool(client, auth_headers, name="Tool B", tool_type="database", config=DB_TOOL_CONFIG)

        resp = await client.get("/api/v1/tools/", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        names = [t["name"] for t in data]
        assert "Tool A" in names
        assert "Tool B" in names

    async def test_list_masks_secrets(self, client: AsyncClient, auth_headers):
        """Ensure listing masks sensitive values."""
        await _create_tool(client, auth_headers, name="Secret Tool")

        resp = await client.get("/api/v1/tools/", headers=auth_headers)
        data = resp.json()
        assert len(data) == 1
        assert data[0]["config"]["headers"]["Authorization"] == "****"

    async def test_list_excludes_deleted(self, client: AsyncClient, auth_headers):
        tool = await _create_tool(client, auth_headers, name="Will Delete")
        await client.delete(f"/api/v1/tools/{tool['id']}", headers=auth_headers)

        resp = await client.get("/api/v1/tools/", headers=auth_headers)
        assert resp.json() == []

    async def test_list_no_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/tools/")
        assert resp.status_code == 401


# ===========================================================================
# UPDATE
# ===========================================================================


class TestUpdateTool:
    """PUT /api/v1/tools/{id}"""

    async def test_update_name(self, client: AsyncClient, auth_headers):
        tool = await _create_tool(client, auth_headers, name="Old Name")

        resp = await client.put(
            f"/api/v1/tools/{tool['id']}",
            json={"name": "New Name"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "New Name"

    async def test_update_description(self, client: AsyncClient, auth_headers):
        tool = await _create_tool(client, auth_headers, name="Desc Tool")

        resp = await client.put(
            f"/api/v1/tools/{tool['id']}",
            json={"description": "Updated description"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated description"

    async def test_update_config(self, client: AsyncClient, auth_headers):
        tool = await _create_tool(client, auth_headers, name="Config Tool")

        new_config = {
            "url": "https://new-api.example.com/v2",
            "method": "POST",
            "headers": {},
        }
        resp = await client.put(
            f"/api/v1/tools/{tool['id']}",
            json={"config": new_config},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["config"]["url"] == "https://new-api.example.com/v2"

    async def test_update_tool_type_with_valid_config(self, client: AsyncClient, auth_headers):
        """Changing tool_type should validate config against new type."""
        tool = await _create_tool(
            client, auth_headers, name="Type Change",
            tool_type="file_system", config=FS_TOOL_CONFIG,
        )

        resp = await client.put(
            f"/api/v1/tools/{tool['id']}",
            json={"tool_type": "database", "config": DB_TOOL_CONFIG},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["tool_type"] == "database"

    async def test_update_duplicate_name_conflict(self, client: AsyncClient, auth_headers):
        await _create_tool(client, auth_headers, name="Existing Name")
        tool2 = await _create_tool(client, auth_headers, name="Other Name")

        resp = await client.put(
            f"/api/v1/tools/{tool2['id']}",
            json={"name": "Existing Name"},
            headers=auth_headers,
        )
        assert resp.status_code == 409

    async def test_update_same_name_ok(self, client: AsyncClient, auth_headers):
        """Updating a tool's own name to the same value should not conflict."""
        tool = await _create_tool(client, auth_headers, name="Keep Name")

        resp = await client.put(
            f"/api/v1/tools/{tool['id']}",
            json={"name": "Keep Name", "description": "Updated desc"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated desc"

    async def test_update_not_found(self, client: AsyncClient, auth_headers):
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.put(
            f"/api/v1/tools/{fake_id}",
            json={"name": "Ghost"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_update_no_auth(self, client: AsyncClient, auth_headers):
        tool = await _create_tool(client, auth_headers, name="Auth Tool")

        resp = await client.put(
            f"/api/v1/tools/{tool['id']}", json={"name": "Hacked"}
        )
        assert resp.status_code == 401

    async def test_update_invalid_config_for_type(self, client: AsyncClient, auth_headers):
        """Updating config with invalid data for the tool_type should fail."""
        tool = await _create_tool(client, auth_headers, name="Bad Config Update")

        resp = await client.put(
            f"/api/v1/tools/{tool['id']}",
            json={"config": {"method": "PATCH"}},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    async def test_update_preserves_masked_api_header_secret(self, client: AsyncClient, auth_headers):
        tool = await _create_tool(client, auth_headers, name="Mask Preserve API")

        update_resp = await client.put(
            f"/api/v1/tools/{tool['id']}",
            json={
                "config": {
                    "url": "https://api.example.com/data",
                    "method": "GET",
                    "headers": {"Authorization": "****"},
                }
            },
            headers=auth_headers,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["config"]["headers"]["Authorization"] == "****"

        safe_response = {"status_code": 200, "body_json": {"ok": True}, "body_text": "{}"}
        with patch(
            "app.engine.tools.executor.safe_http_request",
            new=AsyncMock(return_value=safe_response),
        ):
            test_resp = await client.post(
                f"/api/v1/tools/{tool['id']}/test",
                json={"test_input": "ping"},
                headers=auth_headers,
            )
        assert test_resp.status_code == 200
        assert test_resp.json()["success"] is True

    async def test_update_api_tool_allows_partial_header_update(self, client: AsyncClient, auth_headers):
        tool = await _create_tool(client, auth_headers, name="API Partial Update")

        update_resp = await client.put(
            f"/api/v1/tools/{tool['id']}",
            json={
                "config": {
                    "headers": {"Authorization": "****"},
                }
            },
            headers=auth_headers,
        )
        assert update_resp.status_code == 200
        assert update_resp.json()["config"]["headers"]["Authorization"] == "****"

    async def test_update_preserves_masked_database_connection_string(self, client: AsyncClient, auth_headers):
        tool = await _create_tool(
            client,
            auth_headers,
            name="Mask Preserve DB",
            tool_type="database",
            config=DB_TOOL_CONFIG,
        )

        update_resp = await client.put(
            f"/api/v1/tools/{tool['id']}",
            json={
                "config": {
                    "connection_string": "postgresql://user:****@host:5432/mydb",
                    "query_template": "SELECT * FROM table WHERE id = {input}",
                }
            },
            headers=auth_headers,
        )
        assert update_resp.status_code == 200
        assert "****" in update_resp.json()["config"]["connection_string"]


# ===========================================================================
# DELETE (soft delete)
# ===========================================================================


class TestDeleteTool:
    """DELETE /api/v1/tools/{id}"""

    async def test_delete_success(self, client: AsyncClient, auth_headers):
        tool = await _create_tool(client, auth_headers, name="Delete Me")

        resp = await client.delete(
            f"/api/v1/tools/{tool['id']}", headers=auth_headers
        )
        assert resp.status_code == 204

        # Should not appear in list
        list_resp = await client.get("/api/v1/tools/", headers=auth_headers)
        assert list_resp.json() == []

    async def test_delete_not_found(self, client: AsyncClient, auth_headers):
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.delete(
            f"/api/v1/tools/{fake_id}", headers=auth_headers
        )
        assert resp.status_code == 404

    async def test_delete_no_auth(self, client: AsyncClient, auth_headers):
        tool = await _create_tool(client, auth_headers, name="No Auth Del")

        resp = await client.delete(f"/api/v1/tools/{tool['id']}")
        assert resp.status_code == 401

    async def test_delete_idempotent(self, client: AsyncClient, auth_headers):
        """Deleting an already deleted tool should return 404."""
        tool = await _create_tool(client, auth_headers, name="Double Delete")

        await client.delete(f"/api/v1/tools/{tool['id']}", headers=auth_headers)

        resp = await client.delete(
            f"/api/v1/tools/{tool['id']}", headers=auth_headers
        )
        assert resp.status_code == 404

    async def test_delete_frees_name(self, client: AsyncClient, auth_headers):
        """Soft-deleted tools do not block creating a new active tool with the same name."""
        tool = await _create_tool(client, auth_headers, name="Reuse Name")
        await client.delete(f"/api/v1/tools/{tool['id']}", headers=auth_headers)

        resp = await client.post(
            "/api/v1/tools/",
            json={
                "name": "Reuse Name",
                "tool_type": "api",
                "config": API_TOOL_CONFIG,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "Reuse Name"


# ===========================================================================
# TEST TOOL
# ===========================================================================


class TestTestTool:
    """POST /api/v1/tools/{id}/test"""

    async def test_test_database_tool(self, client: AsyncClient, auth_headers):
        tool = await _create_tool(
            client, auth_headers, name="DB Test",
            tool_type="database",
            config={"connection_string": "sqlite://", "query_template": "SELECT 1 AS value"},
        )

        resp = await client.post(
            f"/api/v1/tools/{tool['id']}/test",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "latency_ms" in data
        assert data["latency_ms"] >= 0

    async def test_test_file_system_tool(self, client: AsyncClient, auth_headers, tmp_path):
        tool = await _create_tool(
            client, auth_headers, name="FS Test",
            tool_type="file_system",
            config={"base_path": str(tmp_path), "allowed_extensions": [".csv", ".json"]},
        )

        resp = await client.post(
            f"/api/v1/tools/{tool['id']}/test",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True

    async def test_test_api_tool_with_mock(self, client: AsyncClient, auth_headers):
        """Test API tool with mocked httpx to avoid real HTTP calls."""
        tool = await _create_tool(client, auth_headers, name="API Mock Test")

        safe_response = {"status_code": 200, "body_json": {"result": "ok"}, "body_text": "{}"}
        with patch(
            "app.engine.tools.executor.safe_http_request",
            new=AsyncMock(return_value=safe_response),
        ):
            resp = await client.post(
                f"/api/v1/tools/{tool['id']}/test",
                json={"test_input": "hello"},
                headers=auth_headers,
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert "latency_ms" in data

    async def test_test_not_found(self, client: AsyncClient, auth_headers):
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.post(
            f"/api/v1/tools/{fake_id}/test",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_test_no_auth(self, client: AsyncClient, auth_headers):
        tool = await _create_tool(client, auth_headers, name="No Auth Test")

        resp = await client.post(f"/api/v1/tools/{tool['id']}/test", json={})
        assert resp.status_code == 401

    async def test_test_as_viewer_forbidden(self, client: AsyncClient, auth_headers):
        tool = await _create_tool(client, auth_headers, name="Viewer Forbidden Test")

        # invite viewer user in same tenant
        invite_resp = await client.post(
            "/api/v1/tenants/invite",
            json={"email": "tools-viewer@test.com", "role": "viewer"},
            headers=auth_headers,
        )
        assert invite_resp.status_code == 201
        viewer = invite_resp.json()

        from app.core.security import create_access_token

        viewer_token = create_access_token(
            user_id=uuid.UUID(viewer["id"]),
            tenant_id=uuid.UUID(viewer["tenant_id"]),
            role="viewer",
        )
        viewer_headers = {"Authorization": f"Bearer {viewer_token}"}

        resp = await client.post(
            f"/api/v1/tools/{tool['id']}/test",
            json={},
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    async def test_test_api_tool_blocks_private_url_when_bypassing_create_checks(
        self, client: AsyncClient, auth_headers
    ):
        with patch("app.services.tool_service._assert_safe_api_url"):
            tool = await _create_tool(
                client,
                auth_headers,
                name="Runtime Private Host",
                tool_type="api",
                config=UNSAFE_API_TOOL_CONFIG,
            )

        resp = await client.post(
            f"/api/v1/tools/{tool['id']}/test",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is False
        assert "https" in data["response"].lower()

    async def test_test_api_tool_blocks_private_dns_resolution(self, client: AsyncClient, auth_headers):
        tool = await _create_tool(
            client,
            auth_headers,
            name="Runtime Private DNS",
            tool_type="api",
            config={
                "url": "https://safe.example.com/data",
                "method": "GET",
                "headers": {},
            },
        )

        with patch("app.engine.tools.safe_http.resolve_public_addresses", return_value={"127.0.0.1"}):
            resp = await client.post(
                f"/api/v1/tools/{tool['id']}/test",
                json={},
                headers=auth_headers,
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["success"] is False
            assert "restricted network" in data["response"].lower()

    async def test_update_api_tool_requires_https_url(self, client: AsyncClient, auth_headers):
        tool = await _create_tool(client, auth_headers, name="API Update HTTPS")

        resp = await client.put(
            f"/api/v1/tools/{tool['id']}",
            json={
                "config": {
                    "url": "http://api.example.com/data",
                    "method": "GET",
                    "headers": {},
                }
            },
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "https" in resp.json()["detail"].lower()

# ===========================================================================
# TENANT ISOLATION
# ===========================================================================


class TestToolTenantIsolation:
    """Ensure tools are scoped to their tenant."""

    async def test_cannot_list_other_tenant_tools(
        self, client: AsyncClient, auth_headers
    ):
        await _create_tool(client, auth_headers, name="Tenant 1 Tool")

        # Create second tenant
        resp2 = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "t2tools@test.com",
                "password": "password123",
                "full_name": "Tenant 2 Owner",
                "tenant_name": "Tenant Two Corp",
            },
        )
        assert resp2.status_code == 201
        other_headers = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

        list_resp = await client.get("/api/v1/tools/", headers=other_headers)
        assert list_resp.json() == []

    async def test_cannot_update_other_tenant_tool(
        self, client: AsyncClient, auth_headers
    ):
        tool = await _create_tool(client, auth_headers, name="Tenant 1 Only")

        resp2 = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "t2tools2@test.com",
                "password": "password123",
                "full_name": "Other",
                "tenant_name": "Other Tools Corp",
            },
        )
        other_headers = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

        resp = await client.put(
            f"/api/v1/tools/{tool['id']}",
            json={"name": "Hijacked"},
            headers=other_headers,
        )
        assert resp.status_code == 404

    async def test_cannot_delete_other_tenant_tool(
        self, client: AsyncClient, auth_headers
    ):
        tool = await _create_tool(client, auth_headers, name="Tenant 1 Tool Only")

        resp2 = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "t2tools3@test.com",
                "password": "password123",
                "full_name": "Other",
                "tenant_name": "Other Corp Tools",
            },
        )
        other_headers = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

        resp = await client.delete(
            f"/api/v1/tools/{tool['id']}", headers=other_headers
        )
        assert resp.status_code == 404

    async def test_cannot_test_other_tenant_tool(
        self, client: AsyncClient, auth_headers
    ):
        tool = await _create_tool(client, auth_headers, name="Tenant 1 Test Tool")

        resp2 = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "t2tools4@test.com",
                "password": "password123",
                "full_name": "Other",
                "tenant_name": "Other Test Corp",
            },
        )
        other_headers = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

        resp = await client.post(
            f"/api/v1/tools/{tool['id']}/test",
            json={},
            headers=other_headers,
        )
        assert resp.status_code == 404

    async def test_same_name_different_tenants_ok(
        self, client: AsyncClient, auth_headers
    ):
        """Two different tenants should be able to have tools with the same name."""
        await _create_tool(client, auth_headers, name="Shared Name")

        resp2 = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "t2tools5@test.com",
                "password": "password123",
                "full_name": "Tenant 2",
                "tenant_name": "Tenant Two Tools",
            },
        )
        assert resp2.status_code == 201
        other_headers = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

        resp = await client.post(
            "/api/v1/tools/",
            json={
                "name": "Shared Name",
                "tool_type": "api",
                "config": API_TOOL_CONFIG,
            },
            headers=other_headers,
        )
        assert resp.status_code == 201
