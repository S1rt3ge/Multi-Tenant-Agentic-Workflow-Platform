"""Tests for M4: Execution Engine — API endpoints, service, compiler, cost."""

import pytest
import uuid
from unittest.mock import patch, AsyncMock, MagicMock
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _create_workflow(client: AsyncClient, headers: dict, name: str = "Exec Test WF") -> dict:
    """Create a workflow via API."""
    resp = await client.post(
        "/api/v1/workflows/",
        json={"name": name, "description": "For execution tests"},
        headers=headers,
    )
    assert resp.status_code == 201, f"Create workflow failed: {resp.text}"
    return resp.json()


async def _setup_workflow_with_agents(client: AsyncClient, headers: dict) -> dict:
    """Create workflow + definition + agent configs so it's executable."""
    wf = await _create_workflow(client, headers)
    wf_id = wf["id"]

    # Update workflow definition with 2 nodes and 1 edge
    definition = {
        "nodes": [
            {"id": "node-1", "type": "agentNode", "position": {"x": 0, "y": 0}, "data": {"label": "Analyzer"}},
            {"id": "node-2", "type": "agentNode", "position": {"x": 200, "y": 0}, "data": {"label": "Validator"}},
        ],
        "edges": [
            {"id": "e1-2", "source": "node-1", "target": "node-2"},
        ],
    }

    resp = await client.put(
        f"/api/v1/workflows/{wf_id}",
        json={"definition": definition},
        headers=headers,
    )
    assert resp.status_code == 200, f"Update workflow failed: {resp.text}"

    # Create agent configs for both nodes
    for node_id, name, role in [("node-1", "Analyzer Agent", "analyzer"), ("node-2", "Validator Agent", "validator")]:
        resp = await client.post(
            f"/api/v1/workflows/{wf_id}/agents/",
            json={
                "node_id": node_id,
                "name": name,
                "role": role,
                "system_prompt": f"You are a {role}.",
                "model": "gpt-4o-mini",
            },
            headers=headers,
        )
        assert resp.status_code == 201, f"Create agent failed: {resp.text}"

    return wf


async def _setup_single_node_workflow(client: AsyncClient, headers: dict) -> dict:
    """Create workflow with 1 node for simpler tests."""
    wf = await _create_workflow(client, headers, name="Single Node WF")
    wf_id = wf["id"]

    definition = {
        "nodes": [
            {"id": "node-1", "type": "agentNode", "position": {"x": 0, "y": 0}, "data": {"label": "Agent"}},
        ],
        "edges": [],
    }

    resp = await client.put(
        f"/api/v1/workflows/{wf_id}",
        json={"definition": definition},
        headers=headers,
    )
    assert resp.status_code == 200

    resp = await client.post(
        f"/api/v1/workflows/{wf_id}/agents/",
        json={
            "node_id": "node-1",
            "name": "Solo Agent",
            "role": "analyzer",
            "system_prompt": "Analyze input.",
            "model": "gpt-4o-mini",
        },
        headers=headers,
    )
    assert resp.status_code == 201

    return wf


# ===========================================================================
# COST CALCULATION
# ===========================================================================


class TestCostCalculation:
    """Test engine/cost.py functions."""

    def test_gpt4o_cost(self):
        from app.engine.cost import calculate_cost
        cost = calculate_cost("gpt-4o", 1000, 500)
        expected = (1000 * 2.50 + 500 * 10.00) / 1_000_000
        assert abs(cost - expected) < 1e-10

    def test_gpt4o_mini_cost(self):
        from app.engine.cost import calculate_cost
        cost = calculate_cost("gpt-4o-mini", 1000, 500)
        expected = (1000 * 0.15 + 500 * 0.60) / 1_000_000
        assert abs(cost - expected) < 1e-10

    def test_claude_sonnet_cost(self):
        from app.engine.cost import calculate_cost
        cost = calculate_cost("claude-sonnet", 1000, 500)
        expected = (1000 * 3.00 + 500 * 15.00) / 1_000_000
        assert abs(cost - expected) < 1e-10

    def test_claude_opus_cost(self):
        from app.engine.cost import calculate_cost
        cost = calculate_cost("claude-opus", 1000, 500)
        expected = (1000 * 15.00 + 500 * 75.00) / 1_000_000
        assert abs(cost - expected) < 1e-10

    def test_unknown_model_fallback(self):
        from app.engine.cost import calculate_cost
        # Unknown model falls back to gpt-4o pricing
        cost = calculate_cost("unknown-model", 1000, 500)
        expected = (1000 * 2.50 + 500 * 10.00) / 1_000_000
        assert abs(cost - expected) < 1e-10

    def test_zero_tokens(self):
        from app.engine.cost import calculate_cost
        cost = calculate_cost("gpt-4o", 0, 0)
        assert cost == 0.0

    def test_estimate_cost(self):
        from app.engine.cost import estimate_cost
        cost = estimate_cost("gpt-4o-mini", 5000, 1000)
        expected = (5000 * 0.15 + 1000 * 0.60) / 1_000_000
        assert abs(cost - expected) < 1e-10


# ===========================================================================
# COMPILER VALIDATION
# ===========================================================================


class TestCompilerValidation:
    """Test engine/compiler.py validation."""

    def test_validate_empty_nodes(self):
        from app.engine.compiler import validate_definition, CompilationError
        with pytest.raises(CompilationError, match="no nodes"):
            validate_definition({"nodes": [], "edges": []})

    def test_validate_orphan_nodes(self):
        from app.engine.compiler import validate_definition, CompilationError
        with pytest.raises(CompilationError, match="Orphan"):
            validate_definition({
                "nodes": [
                    {"id": "a"},
                    {"id": "b"},
                    {"id": "c"},
                ],
                "edges": [
                    {"source": "a", "target": "b"},
                ],
            })

    def test_validate_unknown_source(self):
        from app.engine.compiler import validate_definition, CompilationError
        with pytest.raises(CompilationError, match="unknown source"):
            validate_definition({
                "nodes": [{"id": "a"}],
                "edges": [{"source": "z", "target": "a"}],
            })

    def test_validate_unknown_target(self):
        from app.engine.compiler import validate_definition, CompilationError
        with pytest.raises(CompilationError, match="unknown target"):
            validate_definition({
                "nodes": [{"id": "a"}],
                "edges": [{"source": "a", "target": "z"}],
            })

    def test_validate_single_node_ok(self):
        from app.engine.compiler import validate_definition
        # Should not raise for single node with no edges
        validate_definition({"nodes": [{"id": "a"}], "edges": []})

    def test_validate_connected_graph(self):
        from app.engine.compiler import validate_definition
        validate_definition({
            "nodes": [{"id": "a"}, {"id": "b"}],
            "edges": [{"source": "a", "target": "b"}],
        })

    def test_validate_multi_nodes_no_edges(self):
        from app.engine.compiler import validate_definition, CompilationError
        with pytest.raises(CompilationError, match="disconnected"):
            validate_definition({
                "nodes": [{"id": "a"}, {"id": "b"}],
                "edges": [],
            })


# ===========================================================================
# TOPOLOGICAL SORT
# ===========================================================================


class TestTopologicalSort:
    """Test executor._topological_sort."""

    def test_linear(self):
        from app.engine.executor import _topological_sort
        nodes = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        edges = [{"source": "a", "target": "b"}, {"source": "b", "target": "c"}]
        result = _topological_sort(nodes, edges)
        assert result == ["a", "b", "c"]

    def test_single_node(self):
        from app.engine.executor import _topological_sort
        result = _topological_sort([{"id": "x"}], [])
        assert result == ["x"]

    def test_fan_out(self):
        from app.engine.executor import _topological_sort
        nodes = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        edges = [{"source": "a", "target": "b"}, {"source": "a", "target": "c"}]
        result = _topological_sort(nodes, edges)
        assert result[0] == "a"
        assert set(result) == {"a", "b", "c"}

    def test_fan_in(self):
        from app.engine.executor import _topological_sort
        nodes = [{"id": "a"}, {"id": "b"}, {"id": "c"}]
        edges = [{"source": "a", "target": "c"}, {"source": "b", "target": "c"}]
        result = _topological_sort(nodes, edges)
        assert result[-1] == "c"

    def test_cyclic_fallback(self):
        from app.engine.executor import _topological_sort
        nodes = [{"id": "a"}, {"id": "b"}]
        edges = [{"source": "a", "target": "b"}, {"source": "b", "target": "a"}]
        result = _topological_sort(nodes, edges)
        # Should return all nodes even with cycle
        assert set(result) == {"a", "b"}


# ===========================================================================
# EXECUTE ENDPOINT
# ===========================================================================


class TestStartExecution:
    """POST /api/v1/workflows/{wf_id}/execute"""

    async def test_execute_no_auth(self, client: AsyncClient):
        resp = await client.post(f"/api/v1/workflows/{uuid.uuid4()}/execute", json={})
        assert resp.status_code == 403

    async def test_execute_workflow_not_found(self, client: AsyncClient, auth_headers):
        fake_id = str(uuid.uuid4())
        resp = await client.post(
            f"/api/v1/workflows/{fake_id}/execute",
            json={"input_data": {"text": "test"}},
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_execute_empty_workflow(self, client: AsyncClient, auth_headers):
        """Workflow with no nodes should return 400."""
        wf = await _create_workflow(client, auth_headers)
        resp = await client.post(
            f"/api/v1/workflows/{wf['id']}/execute",
            json={"input_data": {"text": "test"}},
            headers=auth_headers,
        )
        assert resp.status_code == 400
        assert "no nodes" in resp.json()["detail"].lower()

    async def test_execute_success_returns_pending(self, client: AsyncClient, auth_headers):
        """With valid workflow + agents, should return 201 with pending status."""
        wf = await _setup_single_node_workflow(client, auth_headers)

        # Mock the background execution since we can't call real LLMs
        with patch("app.api.v1.executions.run_execution", new_callable=AsyncMock):
            resp = await client.post(
                f"/api/v1/workflows/{wf['id']}/execute",
                json={"input_data": {"text": "analyze this"}},
                headers=auth_headers,
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["status"] == "pending"
        assert "execution_id" in data

    async def test_execute_no_input_data(self, client: AsyncClient, auth_headers):
        """Execution with null input_data should succeed."""
        wf = await _setup_single_node_workflow(client, auth_headers)

        with patch("app.api.v1.executions.run_execution", new_callable=AsyncMock):
            resp = await client.post(
                f"/api/v1/workflows/{wf['id']}/execute",
                json={},
                headers=auth_headers,
            )
        assert resp.status_code == 201

    async def test_execute_budget_exceeded(self, client: AsyncClient, auth_headers, db_session):
        """Budget exceeded should return 422."""
        wf = await _setup_single_node_workflow(client, auth_headers)

        # Drain the tenant budget
        from sqlalchemy import update
        from app.models.tenant import Tenant
        await db_session.execute(
            update(Tenant).values(tokens_used_this_month=999999, monthly_token_budget=100)
        )
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/workflows/{wf['id']}/execute",
            json={"input_data": {"text": "test"}},
            headers=auth_headers,
        )
        assert resp.status_code == 422
        assert "budget" in resp.json()["detail"].lower()

    async def test_execute_free_plan_blocks_second_active_execution(
        self, client: AsyncClient, auth_headers
    ):
        """Free plan allows only one pending/running execution at a time."""
        wf = await _setup_single_node_workflow(client, auth_headers)

        with patch("app.api.v1.executions.run_execution", new_callable=AsyncMock):
            first_resp = await client.post(
                f"/api/v1/workflows/{wf['id']}/execute",
                json={"input_data": {"text": "first"}},
                headers=auth_headers,
            )
            second_resp = await client.post(
                f"/api/v1/workflows/{wf['id']}/execute",
                json={"input_data": {"text": "second"}},
                headers=auth_headers,
            )

        assert first_resp.status_code == 201
        assert second_resp.status_code == 409
        assert "concurrent execution limit" in second_resp.json()["detail"].lower()

    async def test_execute_completed_execution_does_not_consume_slot(
        self, client: AsyncClient, auth_headers, db_session
    ):
        """Completed executions should not count against the concurrency cap."""
        wf = await _setup_single_node_workflow(client, auth_headers)

        with patch("app.api.v1.executions.run_execution", new_callable=AsyncMock):
            first_resp = await client.post(
                f"/api/v1/workflows/{wf['id']}/execute",
                json={"input_data": {"text": "first"}},
                headers=auth_headers,
            )

        from sqlalchemy import update as sa_update
        from app.models.execution import Execution

        await db_session.execute(
            sa_update(Execution)
            .where(Execution.id == uuid.UUID(first_resp.json()["execution_id"]))
            .values(status="completed")
        )
        await db_session.commit()

        with patch("app.api.v1.executions.run_execution", new_callable=AsyncMock):
            second_resp = await client.post(
                f"/api/v1/workflows/{wf['id']}/execute",
                json={"input_data": {"text": "second"}},
                headers=auth_headers,
            )

        assert second_resp.status_code == 201

    async def test_execute_pro_plan_allows_five_active_then_blocks_sixth(
        self, client: AsyncClient, auth_headers, db_session
    ):
        """Pro plan allows five concurrent executions."""
        wf = await _setup_single_node_workflow(client, auth_headers)

        from sqlalchemy import update as sa_update
        from app.models.tenant import Tenant

        await db_session.execute(
            sa_update(Tenant).values(plan="pro")
        )
        await db_session.commit()

        responses = []
        with patch("app.api.v1.executions.run_execution", new_callable=AsyncMock):
            for idx in range(6):
                responses.append(
                    await client.post(
                        f"/api/v1/workflows/{wf['id']}/execute",
                        json={"input_data": {"text": f"run-{idx}"}},
                        headers=auth_headers,
                    )
                )

        for resp in responses[:5]:
            assert resp.status_code == 201
        assert responses[5].status_code == 409
        assert "plan 'pro'" in responses[5].json()["detail"].lower()


# ===========================================================================
# LIST EXECUTIONS
# ===========================================================================


class TestListExecutions:
    """GET /api/v1/executions"""

    async def test_list_no_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/executions")
        assert resp.status_code == 403

    async def test_list_empty(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/executions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0
        assert data["page"] == 1

    async def test_list_with_executions(self, client: AsyncClient, auth_headers):
        """Create an execution and verify it appears in the list."""
        wf = await _setup_single_node_workflow(client, auth_headers)

        with patch("app.api.v1.executions.run_execution", new_callable=AsyncMock):
            await client.post(
                f"/api/v1/workflows/{wf['id']}/execute",
                json={"input_data": {"text": "test"}},
                headers=auth_headers,
            )

        resp = await client.get("/api/v1/executions", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["workflow_id"] == wf["id"]

    async def test_list_filter_by_workflow(self, client: AsyncClient, auth_headers):
        """Filter executions by workflow_id."""
        wf1 = await _setup_single_node_workflow(client, auth_headers)
        wf2 = await _create_workflow(client, auth_headers, name="Other WF")

        with patch("app.api.v1.executions.run_execution", new_callable=AsyncMock):
            await client.post(
                f"/api/v1/workflows/{wf1['id']}/execute",
                json={"input_data": {"text": "test"}},
                headers=auth_headers,
            )

        resp = await client.get(
            f"/api/v1/executions?workflow_id={wf1['id']}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        resp = await client.get(
            f"/api/v1/executions?workflow_id={wf2['id']}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_list_filter_by_status(self, client: AsyncClient, auth_headers):
        """Filter executions by status."""
        wf = await _setup_single_node_workflow(client, auth_headers)

        with patch("app.api.v1.executions.run_execution", new_callable=AsyncMock):
            await client.post(
                f"/api/v1/workflows/{wf['id']}/execute",
                json={},
                headers=auth_headers,
            )

        resp = await client.get(
            "/api/v1/executions?status_filter=pending",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

        resp = await client.get(
            "/api/v1/executions?status_filter=completed",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json()["total"] == 0

    async def test_list_invalid_status_filter(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/executions?status_filter=invalid",
            headers=auth_headers,
        )
        assert resp.status_code == 400

    async def test_list_pagination(self, client: AsyncClient, auth_headers, db_session):
        """Pagination should still work when the tenant plan allows multiple active runs."""
        wf = await _setup_single_node_workflow(client, auth_headers)

        from sqlalchemy import update as sa_update
        from app.models.tenant import Tenant

        await db_session.execute(sa_update(Tenant).values(plan="pro"))
        await db_session.commit()

        with patch("app.api.v1.executions.run_execution", new_callable=AsyncMock):
            for _ in range(3):
                await client.post(
                    f"/api/v1/workflows/{wf['id']}/execute",
                    json={},
                    headers=auth_headers,
                )

        resp = await client.get(
            "/api/v1/executions?page=1&per_page=2",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["items"]) == 2
        assert data["page"] == 1

        resp = await client.get(
            "/api/v1/executions?page=2&per_page=2",
            headers=auth_headers,
        )
        data = resp.json()
        assert len(data["items"]) == 1


# ===========================================================================
# GET EXECUTION
# ===========================================================================


class TestGetExecution:
    """GET /api/v1/executions/{id}"""

    async def test_get_no_auth(self, client: AsyncClient):
        resp = await client.get(f"/api/v1/executions/{uuid.uuid4()}")
        assert resp.status_code == 403

    async def test_get_not_found(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            f"/api/v1/executions/{uuid.uuid4()}",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_get_success(self, client: AsyncClient, auth_headers):
        wf = await _setup_single_node_workflow(client, auth_headers)

        with patch("app.api.v1.executions.run_execution", new_callable=AsyncMock):
            create_resp = await client.post(
                f"/api/v1/workflows/{wf['id']}/execute",
                json={"input_data": {"text": "test"}},
                headers=auth_headers,
            )

        exec_id = create_resp.json()["execution_id"]
        resp = await client.get(
            f"/api/v1/executions/{exec_id}",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == exec_id
        assert data["status"] == "pending"
        assert data["workflow_id"] == wf["id"]
        assert data["input_data"] == {"text": "test"}
        assert data["total_tokens"] == 0
        assert data["total_cost"] == 0.0


# ===========================================================================
# GET EXECUTION LOGS
# ===========================================================================


class TestGetExecutionLogs:
    """GET /api/v1/executions/{id}/logs"""

    async def test_logs_no_auth(self, client: AsyncClient):
        resp = await client.get(f"/api/v1/executions/{uuid.uuid4()}/logs")
        assert resp.status_code == 403

    async def test_logs_not_found(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            f"/api/v1/executions/{uuid.uuid4()}/logs",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_logs_empty(self, client: AsyncClient, auth_headers):
        """Newly created execution has no logs."""
        wf = await _setup_single_node_workflow(client, auth_headers)

        with patch("app.api.v1.executions.run_execution", new_callable=AsyncMock):
            create_resp = await client.post(
                f"/api/v1/workflows/{wf['id']}/execute",
                json={},
                headers=auth_headers,
            )

        exec_id = create_resp.json()["execution_id"]
        resp = await client.get(
            f"/api/v1/executions/{exec_id}/logs",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_logs_with_data(self, client: AsyncClient, auth_headers, db_session):
        """Manually insert a log and verify it's returned."""
        wf = await _setup_single_node_workflow(client, auth_headers)

        with patch("app.api.v1.executions.run_execution", new_callable=AsyncMock):
            create_resp = await client.post(
                f"/api/v1/workflows/{wf['id']}/execute",
                json={},
                headers=auth_headers,
            )

        exec_id = create_resp.json()["execution_id"]

        # Insert log directly
        from app.models.execution import ExecutionLog
        log = ExecutionLog(
            execution_id=uuid.UUID(exec_id),
            step_number=1,
            agent_name="Test Agent",
            action="llm_call",
            input_data={"messages": [{"role": "user", "content": "hi"}]},
            output_data={"content": "hello"},
            tokens_used=150,
            cost=0.001,
            decision_reasoning="Testing",
            duration_ms=500,
        )
        db_session.add(log)
        await db_session.commit()

        resp = await client.get(
            f"/api/v1/executions/{exec_id}/logs",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        logs = resp.json()
        assert len(logs) == 1
        assert logs[0]["step_number"] == 1
        assert logs[0]["agent_name"] == "Test Agent"
        assert logs[0]["action"] == "llm_call"
        assert logs[0]["tokens_used"] == 150
        assert logs[0]["cost"] == 0.001


# ===========================================================================
# CANCEL EXECUTION
# ===========================================================================


class TestCancelExecution:
    """POST /api/v1/executions/{id}/cancel"""

    async def test_cancel_no_auth(self, client: AsyncClient):
        resp = await client.post(f"/api/v1/executions/{uuid.uuid4()}/cancel")
        assert resp.status_code == 403

    async def test_cancel_not_found(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            f"/api/v1/executions/{uuid.uuid4()}/cancel",
            headers=auth_headers,
        )
        assert resp.status_code == 404

    async def test_cancel_pending(self, client: AsyncClient, auth_headers):
        """Cancel a pending execution should set status=cancelled immediately."""
        wf = await _setup_single_node_workflow(client, auth_headers)

        with patch("app.api.v1.executions.run_execution", new_callable=AsyncMock):
            create_resp = await client.post(
                f"/api/v1/workflows/{wf['id']}/execute",
                json={},
                headers=auth_headers,
            )

        exec_id = create_resp.json()["execution_id"]
        resp = await client.post(
            f"/api/v1/executions/{exec_id}/cancel",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "cancelled"
        assert data["error_message"] == "Execution cancelled by user"

    async def test_cancel_already_completed(self, client: AsyncClient, auth_headers, db_session):
        """Cancel a completed execution should return 409."""
        wf = await _setup_single_node_workflow(client, auth_headers)

        with patch("app.api.v1.executions.run_execution", new_callable=AsyncMock):
            create_resp = await client.post(
                f"/api/v1/workflows/{wf['id']}/execute",
                json={},
                headers=auth_headers,
            )

        exec_id = create_resp.json()["execution_id"]

        # Manually mark as completed
        from sqlalchemy import update as sa_update
        from app.models.execution import Execution
        await db_session.execute(
            sa_update(Execution)
            .where(Execution.id == uuid.UUID(exec_id))
            .values(status="completed")
        )
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/executions/{exec_id}/cancel",
            headers=auth_headers,
        )
        assert resp.status_code == 409
        assert "cannot cancel" in resp.json()["detail"].lower()

    async def test_cancel_already_failed(self, client: AsyncClient, auth_headers, db_session):
        """Cancel a failed execution should return 409."""
        wf = await _setup_single_node_workflow(client, auth_headers)

        with patch("app.api.v1.executions.run_execution", new_callable=AsyncMock):
            create_resp = await client.post(
                f"/api/v1/workflows/{wf['id']}/execute",
                json={},
                headers=auth_headers,
            )

        exec_id = create_resp.json()["execution_id"]

        from sqlalchemy import update as sa_update
        from app.models.execution import Execution
        await db_session.execute(
            sa_update(Execution)
            .where(Execution.id == uuid.UUID(exec_id))
            .values(status="failed")
        )
        await db_session.commit()

        resp = await client.post(
            f"/api/v1/executions/{exec_id}/cancel",
            headers=auth_headers,
        )
        assert resp.status_code == 409


# ===========================================================================
# TENANT ISOLATION
# ===========================================================================


class TestExecutionTenantIsolation:
    """Ensure executions are tenant-isolated."""

    async def test_cannot_see_other_tenant_execution(self, client: AsyncClient, auth_headers):
        """User from one tenant cannot access executions from another tenant."""
        wf = await _setup_single_node_workflow(client, auth_headers)

        with patch("app.api.v1.executions.run_execution", new_callable=AsyncMock):
            create_resp = await client.post(
                f"/api/v1/workflows/{wf['id']}/execute",
                json={},
                headers=auth_headers,
            )

        exec_id = create_resp.json()["execution_id"]

        # Register a second user (different tenant)
        resp2 = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "other@other.com",
                "password": "password123",
                "full_name": "Other User",
                "tenant_name": "Other Corp",
            },
        )
        assert resp2.status_code == 201
        other_headers = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

        # Other tenant cannot GET this execution
        resp = await client.get(
            f"/api/v1/executions/{exec_id}",
            headers=other_headers,
        )
        assert resp.status_code == 404

    async def test_list_only_own_tenant(self, client: AsyncClient, auth_headers):
        """Each tenant only sees their own executions in list."""
        wf = await _setup_single_node_workflow(client, auth_headers)

        with patch("app.api.v1.executions.run_execution", new_callable=AsyncMock):
            await client.post(
                f"/api/v1/workflows/{wf['id']}/execute",
                json={},
                headers=auth_headers,
            )

        # Register second user
        resp2 = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "other2@other.com",
                "password": "password123",
                "full_name": "Other User 2",
                "tenant_name": "Other Corp 2",
            },
        )
        other_headers = {"Authorization": f"Bearer {resp2.json()['access_token']}"}

        # Other tenant sees 0 executions
        resp = await client.get("/api/v1/executions", headers=other_headers)
        assert resp.status_code == 200
        assert resp.json()["total"] == 0


# ===========================================================================
# EXECUTION RESPONSE SCHEMA
# ===========================================================================


class TestExecutionResponseFields:
    """Verify response fields match schema."""

    async def test_execution_has_all_fields(self, client: AsyncClient, auth_headers):
        wf = await _setup_single_node_workflow(client, auth_headers)

        with patch("app.api.v1.executions.run_execution", new_callable=AsyncMock):
            create_resp = await client.post(
                f"/api/v1/workflows/{wf['id']}/execute",
                json={"input_data": {"text": "hello"}},
                headers=auth_headers,
            )

        exec_id = create_resp.json()["execution_id"]
        resp = await client.get(
            f"/api/v1/executions/{exec_id}",
            headers=auth_headers,
        )
        data = resp.json()

        required_fields = [
            "id", "tenant_id", "workflow_id", "status", "input_data",
            "output_data", "total_tokens", "total_cost", "error_message",
            "started_at", "completed_at", "created_at",
        ]
        for field in required_fields:
            assert field in data, f"Missing field: {field}"


# ===========================================================================
# MULTIPLE EXECUTIONS
# ===========================================================================


class TestMultipleExecutions:
    """Test concurrent executions of the same workflow."""

    async def test_multiple_executions_allowed(self, client: AsyncClient, auth_headers, db_session):
        """Paid plans should allow multiple executions of the same workflow."""
        wf = await _setup_single_node_workflow(client, auth_headers)

        from sqlalchemy import update as sa_update
        from app.models.tenant import Tenant

        await db_session.execute(sa_update(Tenant).values(plan="pro"))
        await db_session.commit()

        with patch("app.api.v1.executions.run_execution", new_callable=AsyncMock):
            ids = []
            for i in range(3):
                resp = await client.post(
                    f"/api/v1/workflows/{wf['id']}/execute",
                    json={"input_data": {"text": f"test {i}"}},
                    headers=auth_headers,
                )
                assert resp.status_code == 201
                ids.append(resp.json()["execution_id"])

        # All 3 should be unique
        assert len(set(ids)) == 3

        # List should show 3
        resp = await client.get("/api/v1/executions", headers=auth_headers)
        assert resp.json()["total"] == 3
