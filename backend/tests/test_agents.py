"""Tests for /api/v1/workflows/{wf_id}/agents/* endpoints (M3 — Agent Configs)."""

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_workflow(client: AsyncClient, headers: dict, name: str = "Builder WF") -> dict:
    resp = await client.post("/api/v1/workflows/", json={"name": name}, headers=headers)
    assert resp.status_code == 201, f"Create workflow failed: {resp.text}"
    return resp.json()


async def _create_agent(
    client: AsyncClient,
    headers: dict,
    wf_id: str,
    node_id: str = "node-1",
    name: str = "Agent 1",
    **overrides,
) -> dict:
    payload = {
        "node_id": node_id,
        "name": name,
        "role": "analyzer",
        "system_prompt": "You are a helpful assistant.",
        "model": "gpt-4o",
        "tools": [],
        "memory_type": "buffer",
        "max_tokens": 4096,
        "temperature": 0.7,
        **overrides,
    }
    resp = await client.post(
        f"/api/v1/workflows/{wf_id}/agents/", json=payload, headers=headers
    )
    assert resp.status_code == 201, f"Create agent failed: {resp.text}"
    return resp.json()


# ===========================================================================
# CREATE
# ===========================================================================


class TestCreateAgent:
    """POST /api/v1/workflows/{wf_id}/agents/"""

    async def test_create_success(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)

        resp = await client.post(
            f"/api/v1/workflows/{wf['id']}/agents/",
            json={
                "node_id": "node-1",
                "name": "Data Retriever",
                "role": "retriever",
                "model": "gpt-4o-mini",
                "system_prompt": "You retrieve data.",
                "tools": [{"tool_id": "abc", "name": "search_api"}],
                "memory_type": "summary",
                "max_tokens": 2048,
                "temperature": 0.3,
            },
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "Data Retriever"
        assert data["role"] == "retriever"
        assert data["model"] == "gpt-4o-mini"
        assert data["node_id"] == "node-1"
        assert data["memory_type"] == "summary"
        assert data["max_tokens"] == 2048
        assert data["temperature"] == 0.3
        assert len(data["tools"]) == 1
        assert "id" in data
        assert "workflow_id" in data
        assert "tenant_id" in data

    async def test_create_with_defaults(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)

        resp = await client.post(
            f"/api/v1/workflows/{wf['id']}/agents/",
            json={"node_id": "node-default", "name": "Default Agent"},
            headers=auth_headers,
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["role"] == "analyzer"
        assert data["model"] == "gpt-4o"
        assert data["memory_type"] == "buffer"
        assert data["max_tokens"] == 4096
        assert data["temperature"] == 0.7
        assert data["tools"] == []

    async def test_create_invalid_role(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)

        resp = await client.post(
            f"/api/v1/workflows/{wf['id']}/agents/",
            json={"node_id": "n1", "name": "Bad", "role": "hacker"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "role" in resp.json()["detail"].lower()

    async def test_create_invalid_model(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)

        resp = await client.post(
            f"/api/v1/workflows/{wf['id']}/agents/",
            json={"node_id": "n1", "name": "Bad", "model": "llama-7b"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "model" in resp.json()["detail"].lower()

    async def test_create_invalid_memory_type(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)

        resp = await client.post(
            f"/api/v1/workflows/{wf['id']}/agents/",
            json={"node_id": "n1", "name": "Bad", "memory_type": "graph"},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "memory_type" in resp.json()["detail"].lower()

    async def test_create_duplicate_node_id(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)
        await _create_agent(client, auth_headers, wf["id"], node_id="node-dup")

        resp = await client.post(
            f"/api/v1/workflows/{wf['id']}/agents/",
            json={"node_id": "node-dup", "name": "Duplicate"},
            headers=auth_headers,
        )
        assert resp.status_code == 409
        assert "already exists" in resp.json()["detail"].lower()

    async def test_create_exceeds_agent_limit(self, client: AsyncClient, auth_headers):
        """Default tenant max_agents_per_workflow=3."""
        wf = await _create_workflow(client, auth_headers)
        await _create_agent(client, auth_headers, wf["id"], node_id="n1", name="A1")
        await _create_agent(client, auth_headers, wf["id"], node_id="n2", name="A2")
        await _create_agent(client, auth_headers, wf["id"], node_id="n3", name="A3")

        resp = await client.post(
            f"/api/v1/workflows/{wf['id']}/agents/",
            json={"node_id": "n4", "name": "A4"},
            headers=auth_headers,
        )
        assert resp.status_code == 422
        assert "limit reached" in resp.json()["detail"].lower()

    async def test_create_workflow_not_found(self, client: AsyncClient, auth_headers):
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.post(
            f"/api/v1/workflows/{fake_id}/agents/",
            json={"node_id": "n1", "name": "Orphan"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_create_no_auth(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)
        resp = await client.post(
            f"/api/v1/workflows/{wf['id']}/agents/",
            json={"node_id": "n1", "name": "No Auth"},
        )
        assert resp.status_code == 403

    async def test_create_missing_node_id(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)
        resp = await client.post(
            f"/api/v1/workflows/{wf['id']}/agents/",
            json={"name": "No Node"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_create_max_tokens_out_of_range(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)
        resp = await client.post(
            f"/api/v1/workflows/{wf['id']}/agents/",
            json={"node_id": "n1", "name": "Big", "max_tokens": 99999},
            headers=auth_headers,
        )
        assert resp.status_code == 422

    async def test_create_temperature_out_of_range(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)
        resp = await client.post(
            f"/api/v1/workflows/{wf['id']}/agents/",
            json={"node_id": "n1", "name": "Hot", "temperature": 5.0},
            headers=auth_headers,
        )
        assert resp.status_code == 422


# ===========================================================================
# LIST
# ===========================================================================


class TestListAgents:
    """GET /api/v1/workflows/{wf_id}/agents/"""

    async def test_list_empty(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)
        resp = await client.get(
            f"/api/v1/workflows/{wf['id']}/agents/", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_list_with_agents(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)
        await _create_agent(client, auth_headers, wf["id"], node_id="n1", name="A1")
        await _create_agent(client, auth_headers, wf["id"], node_id="n2", name="A2")

        resp = await client.get(
            f"/api/v1/workflows/{wf['id']}/agents/", headers=auth_headers
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        names = [a["name"] for a in data]
        assert "A1" in names
        assert "A2" in names

    async def test_list_workflow_not_found(self, client: AsyncClient, auth_headers):
        fake_id = "00000000-0000-0000-0000-000000000000"
        resp = await client.get(
            f"/api/v1/workflows/{fake_id}/agents/", headers=auth_headers
        )
        assert resp.status_code == 404

    async def test_list_no_auth(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)
        resp = await client.get(f"/api/v1/workflows/{wf['id']}/agents/")
        assert resp.status_code == 403


# ===========================================================================
# UPDATE
# ===========================================================================


class TestUpdateAgent:
    """PUT /api/v1/workflows/{wf_id}/agents/{agent_id}"""

    async def test_update_name(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)
        agent = await _create_agent(client, auth_headers, wf["id"])

        resp = await client.put(
            f"/api/v1/workflows/{wf['id']}/agents/{agent['id']}",
            json={"name": "Renamed Agent"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["name"] == "Renamed Agent"

    async def test_update_role_and_model(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)
        agent = await _create_agent(client, auth_headers, wf["id"])

        resp = await client.put(
            f"/api/v1/workflows/{wf['id']}/agents/{agent['id']}",
            json={"role": "validator", "model": "claude-sonnet"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["role"] == "validator"
        assert data["model"] == "claude-sonnet"

    async def test_update_system_prompt(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)
        agent = await _create_agent(client, auth_headers, wf["id"])

        resp = await client.put(
            f"/api/v1/workflows/{wf['id']}/agents/{agent['id']}",
            json={"system_prompt": "You are an expert data analyst."},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["system_prompt"] == "You are an expert data analyst."

    async def test_update_tools(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)
        agent = await _create_agent(client, auth_headers, wf["id"])

        tools = [{"tool_id": "t1", "name": "api_search"}, {"tool_id": "t2", "name": "db_query"}]
        resp = await client.put(
            f"/api/v1/workflows/{wf['id']}/agents/{agent['id']}",
            json={"tools": tools},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert len(resp.json()["tools"]) == 2

    async def test_update_temperature_and_tokens(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)
        agent = await _create_agent(client, auth_headers, wf["id"])

        resp = await client.put(
            f"/api/v1/workflows/{wf['id']}/agents/{agent['id']}",
            json={"temperature": 1.5, "max_tokens": 8192, "memory_type": "vector"},
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["temperature"] == 1.5
        assert data["max_tokens"] == 8192
        assert data["memory_type"] == "vector"

    async def test_update_invalid_role(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)
        agent = await _create_agent(client, auth_headers, wf["id"])

        resp = await client.put(
            f"/api/v1/workflows/{wf['id']}/agents/{agent['id']}",
            json={"role": "superhero"},
            headers=auth_headers,
        )
        assert resp.status_code == 400

    async def test_update_not_found(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)
        fake_id = "00000000-0000-0000-0000-000000000000"

        resp = await client.put(
            f"/api/v1/workflows/{wf['id']}/agents/{fake_id}",
            json={"name": "Ghost"},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_update_no_auth(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)
        agent = await _create_agent(client, auth_headers, wf["id"])

        resp = await client.put(
            f"/api/v1/workflows/{wf['id']}/agents/{agent['id']}",
            json={"name": "Hacked"},
        )
        assert resp.status_code == 403


# ===========================================================================
# DELETE
# ===========================================================================


class TestDeleteAgent:
    """DELETE /api/v1/workflows/{wf_id}/agents/{agent_id}"""

    async def test_delete_success(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)
        agent = await _create_agent(client, auth_headers, wf["id"])

        resp = await client.delete(
            f"/api/v1/workflows/{wf['id']}/agents/{agent['id']}",
            headers=auth_headers,
        )
        assert resp.status_code == 204

        # Verify it's gone
        list_resp = await client.get(
            f"/api/v1/workflows/{wf['id']}/agents/", headers=auth_headers
        )
        assert list_resp.json() == []

    async def test_delete_frees_agent_slot(self, client: AsyncClient, auth_headers):
        """Deleting an agent frees the slot for a new one (max_agents_per_workflow=3)."""
        wf = await _create_workflow(client, auth_headers)
        a1 = await _create_agent(client, auth_headers, wf["id"], node_id="n1", name="A1")
        await _create_agent(client, auth_headers, wf["id"], node_id="n2", name="A2")
        await _create_agent(client, auth_headers, wf["id"], node_id="n3", name="A3")

        # At limit
        resp = await client.post(
            f"/api/v1/workflows/{wf['id']}/agents/",
            json={"node_id": "n4", "name": "A4"},
            headers=auth_headers,
        )
        assert resp.status_code == 422

        # Delete one
        await client.delete(
            f"/api/v1/workflows/{wf['id']}/agents/{a1['id']}",
            headers=auth_headers,
        )

        # Now can create
        resp = await client.post(
            f"/api/v1/workflows/{wf['id']}/agents/",
            json={"node_id": "n4", "name": "A4"},
            headers=auth_headers,
        )
        assert resp.status_code == 201

    async def test_delete_not_found(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)
        fake_id = "00000000-0000-0000-0000-000000000000"

        resp = await client.delete(
            f"/api/v1/workflows/{wf['id']}/agents/{fake_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_delete_no_auth(self, client: AsyncClient, auth_headers):
        wf = await _create_workflow(client, auth_headers)
        agent = await _create_agent(client, auth_headers, wf["id"])

        resp = await client.delete(
            f"/api/v1/workflows/{wf['id']}/agents/{agent['id']}"
        )
        assert resp.status_code == 403


# ===========================================================================
# TENANT ISOLATION
# ===========================================================================


class TestAgentTenantIsolation:
    """Ensure agent configs are scoped to their tenant."""

    async def test_cannot_list_other_tenant_agents(
        self, client: AsyncClient, auth_headers
    ):
        wf = await _create_workflow(client, auth_headers)
        await _create_agent(client, auth_headers, wf["id"])

        # Second tenant
        resp2 = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "t2agent@test.com",
                "password": "password123",
                "full_name": "Tenant 2",
                "tenant_name": "Other Corp",
            },
        )
        other_headers = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

        # Can't see workflow -> 404
        resp = await client.get(
            f"/api/v1/workflows/{wf['id']}/agents/", headers=other_headers
        )
        assert resp.status_code == 404

    async def test_cannot_create_agent_in_other_tenant_workflow(
        self, client: AsyncClient, auth_headers
    ):
        wf = await _create_workflow(client, auth_headers)

        resp2 = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "t2agent2@test.com",
                "password": "password123",
                "full_name": "Other",
                "tenant_name": "Other Corp 2",
            },
        )
        other_headers = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

        resp = await client.post(
            f"/api/v1/workflows/{wf['id']}/agents/",
            json={"node_id": "n1", "name": "Injected"},
            headers=other_headers,
        )
        assert resp.status_code == 404

    async def test_cannot_update_other_tenant_agent(
        self, client: AsyncClient, auth_headers
    ):
        wf = await _create_workflow(client, auth_headers)
        agent = await _create_agent(client, auth_headers, wf["id"])

        resp2 = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "t2agent3@test.com",
                "password": "password123",
                "full_name": "Other",
                "tenant_name": "Other Corp 3",
            },
        )
        other_headers = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

        resp = await client.put(
            f"/api/v1/workflows/{wf['id']}/agents/{agent['id']}",
            json={"name": "Hijacked"},
            headers=other_headers,
        )
        assert resp.status_code == 404

    async def test_cannot_delete_other_tenant_agent(
        self, client: AsyncClient, auth_headers
    ):
        wf = await _create_workflow(client, auth_headers)
        agent = await _create_agent(client, auth_headers, wf["id"])

        resp2 = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "t2agent4@test.com",
                "password": "password123",
                "full_name": "Other",
                "tenant_name": "Other Corp 4",
            },
        )
        other_headers = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

        resp = await client.delete(
            f"/api/v1/workflows/{wf['id']}/agents/{agent['id']}",
            headers=other_headers,
        )
        assert resp.status_code == 404
