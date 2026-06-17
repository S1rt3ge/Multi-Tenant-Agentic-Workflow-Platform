"""Tests for M8 Workflow Doctor diagnosis, replay, and patch application."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_config import AgentConfig
from app.models.execution import Execution, ExecutionLog
from app.models.tool_registry import ToolRegistry


async def _create_workflow(
    client: AsyncClient,
    headers: dict,
    definition: dict | None = None,
    name: str = "Doctor WF",
) -> dict:
    resp = await client.post(
        "/api/v1/workflows/",
        json={"name": name, "description": "Workflow Doctor test"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    workflow = resp.json()

    if definition is not None:
        update = await client.put(
            f"/api/v1/workflows/{workflow['id']}",
            json={"definition": definition},
            headers=headers,
        )
        assert update.status_code == 200, update.text
        workflow = update.json()

    return workflow


async def _create_agent(
    client: AsyncClient,
    headers: dict,
    workflow_id: str,
    node_id: str = "node-1",
    model: str = "gpt-4o-mini",
) -> dict:
    resp = await client.post(
        f"/api/v1/workflows/{workflow_id}/agents/",
        json={
            "node_id": node_id,
            "name": "Doctor Agent",
            "role": "analyzer",
            "system_prompt": "You analyze workflow inputs.",
            "model": model,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _force_agent_model(db: AsyncSession, agent_id: str, model: str) -> None:
    agent = await db.get(AgentConfig, uuid.UUID(agent_id))
    assert agent is not None
    agent.model = model
    await db.commit()


async def _create_failed_execution(
    db: AsyncSession,
    tenant_id: str,
    workflow_id: str,
    message: str,
    agent_config_id: str | None = None,
    agent_name: str = "Doctor Agent",
) -> Execution:
    execution = Execution(
        tenant_id=uuid.UUID(tenant_id),
        workflow_id=uuid.UUID(workflow_id),
        status="failed",
        input_data={"text": "doctor test"},
        error_message=message,
    )
    db.add(execution)
    await db.flush()

    db.add(
        ExecutionLog(
            execution_id=execution.id,
            agent_config_id=uuid.UUID(agent_config_id) if agent_config_id else None,
            step_number=1,
            agent_name=agent_name,
            action="error",
            input_data={"messages": [{"role": "user", "content": "doctor test"}]},
            output_data={"error": message},
            tokens_used=0,
            cost=0.0,
            decision_reasoning=message,
            duration_ms=10,
        )
    )
    await db.commit()
    await db.refresh(execution)
    return execution


async def _viewer_headers(client: AsyncClient, owner_headers: dict) -> dict:
    email = f"viewer-{uuid.uuid4()}@test.com"
    invite = await client.post(
        "/api/v1/tenants/invite",
        json={"email": email, "role": "viewer"},
        headers=owner_headers,
    )
    assert invite.status_code == 201, invite.text
    viewer = invite.json()
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": viewer["temporary_password"]},
    )
    assert login.status_code == 200, login.text
    set_password = await client.post(
        "/api/v1/auth/set-password",
        json={"password": "viewersecure123"},
        headers={"Authorization": f"Bearer {login.json()['access_token']}"},
    )
    assert set_password.status_code == 200, set_password.text
    return {"Authorization": f"Bearer {set_password.json()['access_token']}"}


async def _first_suggestion(client: AsyncClient, headers: dict, execution_id: uuid.UUID) -> dict:
    resp = await client.post(
        f"/api/v1/executions/{execution_id}/diagnose",
        json={},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["items"]
    return data["items"][0]


class TestWorkflowDoctorDiagnose:
    async def test_diagnose_missing_provider_key(self, client, auth_headers, db_session):
        definition = {
            "nodes": [{"id": "node-1", "position": {"x": 0, "y": 0}, "data": {}}],
            "edges": [],
        }
        workflow = await _create_workflow(client, auth_headers, definition)
        agent = await _create_agent(client, auth_headers, workflow["id"], model="gpt-4o-mini")
        execution = await _create_failed_execution(
            db_session,
            workflow["tenant_id"],
            workflow["id"],
            "OPENAI_API_KEY not configured",
            agent["id"],
        )

        suggestion = await _first_suggestion(client, auth_headers, execution.id)

        assert suggestion["detector_code"] == "missing_provider_key"
        assert suggestion["severity"] == "high"
        assert suggestion["confidence"] >= 0.9
        assert suggestion["patch"]["operations"] == []

    async def test_diagnose_missing_agent_config(self, client, auth_headers, db_session):
        definition = {
            "nodes": [{"id": "node-missing", "position": {"x": 0, "y": 0}, "data": {}}],
            "edges": [],
        }
        workflow = await _create_workflow(client, auth_headers, definition)
        execution = await _create_failed_execution(
            db_session,
            workflow["tenant_id"],
            workflow["id"],
            "Compilation error: Agent configs missing for nodes: {'node-missing'}",
            None,
            "System",
        )

        suggestion = await _first_suggestion(client, auth_headers, execution.id)

        assert suggestion["detector_code"] == "missing_agent_config"
        assert suggestion["severity"] == "critical"
        assert "node-missing" in suggestion["root_cause"]

    async def test_viewer_can_diagnose_and_list_suggestions(self, client, auth_headers, db_session):
        definition = {
            "nodes": [{"id": "node-1", "position": {"x": 0, "y": 0}, "data": {}}],
            "edges": [],
        }
        workflow = await _create_workflow(client, auth_headers, definition)
        agent = await _create_agent(client, auth_headers, workflow["id"])
        execution = await _create_failed_execution(
            db_session,
            workflow["tenant_id"],
            workflow["id"],
            "Unsupported model: legacy-model",
            agent["id"],
        )
        viewer_headers = await _viewer_headers(client, auth_headers)

        diagnose = await client.post(
            f"/api/v1/executions/{execution.id}/diagnose",
            json={},
            headers=viewer_headers,
        )
        assert diagnose.status_code == 201, diagnose.text

        listed = await client.get(
            f"/api/v1/executions/{execution.id}/fix-suggestions",
            headers=viewer_headers,
        )
        assert listed.status_code == 200, listed.text
        assert listed.json()["total"] == 1

    async def test_diagnose_rejects_running_execution(self, client, auth_headers, db_session):
        workflow = await _create_workflow(client, auth_headers)
        execution = Execution(
            tenant_id=uuid.UUID(workflow["tenant_id"]),
            workflow_id=uuid.UUID(workflow["id"]),
            status="running",
            input_data={"text": "still running"},
        )
        db_session.add(execution)
        await db_session.commit()
        await db_session.refresh(execution)

        resp = await client.post(
            f"/api/v1/executions/{execution.id}/diagnose",
            json={},
            headers=auth_headers,
        )
        assert resp.status_code == 409


class TestWorkflowDoctorReplayAndApply:
    async def test_replay_supported_model_patch_passes(self, client, auth_headers, db_session):
        definition = {
            "nodes": [{"id": "node-1", "position": {"x": 0, "y": 0}, "data": {}}],
            "edges": [],
        }
        workflow = await _create_workflow(client, auth_headers, definition)
        agent = await _create_agent(client, auth_headers, workflow["id"])
        await _force_agent_model(db_session, agent["id"], "legacy-model")
        execution = await _create_failed_execution(
            db_session,
            workflow["tenant_id"],
            workflow["id"],
            "Unsupported model: legacy-model",
            agent["id"],
        )
        suggestion = await _first_suggestion(client, auth_headers, execution.id)

        resp = await client.post(
            f"/api/v1/fix-suggestions/{suggestion['id']}/replay",
            json={"mode": "validation_only"},
            headers=auth_headers,
        )

        assert resp.status_code == 201, resp.text
        data = resp.json()
        assert data["status"] == "passed"
        assert data["result"]["external_calls_executed"] is False

    async def test_apply_model_patch_and_retry_creates_new_execution(
        self, client, auth_headers, db_session
    ):
        definition = {
            "nodes": [{"id": "node-1", "position": {"x": 0, "y": 0}, "data": {}}],
            "edges": [],
        }
        workflow = await _create_workflow(client, auth_headers, definition)
        agent = await _create_agent(client, auth_headers, workflow["id"])
        await _force_agent_model(db_session, agent["id"], "legacy-model")
        execution = await _create_failed_execution(
            db_session,
            workflow["tenant_id"],
            workflow["id"],
            "Unsupported model: legacy-model",
            agent["id"],
        )
        suggestion = await _first_suggestion(client, auth_headers, execution.id)

        replay = await client.post(
            f"/api/v1/fix-suggestions/{suggestion['id']}/replay",
            json={"mode": "validation_only"},
            headers=auth_headers,
        )
        assert replay.status_code == 201, replay.text

        resp = await client.post(
            f"/api/v1/fix-suggestions/{suggestion['id']}/apply",
            json={"retry": True},
            headers=auth_headers,
        )
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert data["status"] == "applied"
        assert data["retry_execution_id"]

        updated_agent = await db_session.get(AgentConfig, uuid.UUID(agent["id"]))
        assert updated_agent.model == "gpt-4o-mini"

        retry_execution = await db_session.get(
            Execution, uuid.UUID(data["retry_execution_id"])
        )
        assert retry_execution.status == "pending"
        assert retry_execution.input_data == execution.input_data

    async def test_viewer_cannot_apply_suggestion(self, client, auth_headers, db_session):
        definition = {
            "nodes": [{"id": "node-1", "position": {"x": 0, "y": 0}, "data": {}}],
            "edges": [],
        }
        workflow = await _create_workflow(client, auth_headers, definition)
        agent = await _create_agent(client, auth_headers, workflow["id"])
        await _force_agent_model(db_session, agent["id"], "legacy-model")
        execution = await _create_failed_execution(
            db_session,
            workflow["tenant_id"],
            workflow["id"],
            "Unsupported model: legacy-model",
            agent["id"],
        )
        suggestion = await _first_suggestion(client, auth_headers, execution.id)
        viewer_headers = await _viewer_headers(client, auth_headers)

        resp = await client.post(
            f"/api/v1/fix-suggestions/{suggestion['id']}/apply",
            json={"retry": False},
            headers=viewer_headers,
        )
        assert resp.status_code == 403

    async def test_cross_tenant_suggestion_is_hidden(
        self, client, auth_headers, db_session
    ):
        definition = {
            "nodes": [{"id": "node-1", "position": {"x": 0, "y": 0}, "data": {}}],
            "edges": [],
        }
        workflow = await _create_workflow(client, auth_headers, definition)
        agent = await _create_agent(client, auth_headers, workflow["id"])
        await _force_agent_model(db_session, agent["id"], "legacy-model")
        execution = await _create_failed_execution(
            db_session,
            workflow["tenant_id"],
            workflow["id"],
            "Unsupported model: legacy-model",
            agent["id"],
        )
        suggestion = await _first_suggestion(client, auth_headers, execution.id)

        other_register = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "doctor-other@test.com",
                "password": "securepass123",
                "full_name": "Other Tenant",
                "tenant_name": "Other Doctor Tenant",
            },
        )
        assert other_register.status_code == 201, other_register.text
        other_headers = {
            "Authorization": f"Bearer {other_register.json()['access_token']}"
        }

        resp = await client.post(
            f"/api/v1/fix-suggestions/{suggestion['id']}/replay",
            json={"mode": "validation_only"},
            headers=other_headers,
        )
        assert resp.status_code == 404

    async def test_apply_blocks_secret_patch_paths(self, client, auth_headers, db_session):
        workflow = await _create_workflow(client, auth_headers)
        execution = await _create_failed_execution(
            db_session,
            workflow["tenant_id"],
            workflow["id"],
            "Manual blocked patch test",
            None,
            "System",
        )
        tool = ToolRegistry(
            tenant_id=uuid.UUID(workflow["tenant_id"]),
            name="Secret Tool",
            description="Tool with secret header",
            tool_type="api",
            config={
                "url": "https://example.com/",
                "method": "GET",
                "headers": {"Authorization": "Bearer secret-token"},
            },
        )
        db_session.add(tool)
        await db_session.flush()

        from app.models.workflow_doctor import WorkflowFixSuggestion

        suggestion = WorkflowFixSuggestion(
            tenant_id=uuid.UUID(workflow["tenant_id"]),
            workflow_id=uuid.UUID(workflow["id"]),
            execution_id=execution.id,
            tool_id=tool.id,
            detector_code="manual_secret_patch",
            title="Blocked secret patch",
            root_cause="A detector attempted to modify a secret header.",
            recommendation="Secret patches must be rejected.",
            confidence=0.5,
            patch={
                "operations": [
                    {
                        "op": "replace",
                        "target_type": "tool",
                        "target_id": str(tool.id),
                        "path": "/config/headers/Authorization",
                        "value": "Bearer new-secret",
                        "secret": True,
                    }
                ]
            },
        )
        db_session.add(suggestion)
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/fix-suggestions/{suggestion.id}/apply",
            json={"retry": False},
            headers=auth_headers,
        )
        assert resp.status_code == 422
        assert "blocked" in resp.json()["detail"].lower()

        stored_tool = await db_session.get(ToolRegistry, tool.id)
        assert stored_tool.config["headers"]["Authorization"] == "Bearer secret-token"
