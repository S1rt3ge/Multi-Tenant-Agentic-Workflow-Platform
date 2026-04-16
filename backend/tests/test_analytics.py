"""
Tests for M6 — Dashboard & Analytics.

Covers:
- Overview KPI (with data, empty, period filter)
- Cost Timeline (daily aggregation, zero-fill missing days)
- Workflow Breakdown (per-workflow stats, cost percentage)
- Export (CSV, JSON, date filters, empty)
- Tenant Isolation (cannot see other tenant data)
- Cache (basic invalidation)
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import AsyncClient

from app.models.execution import Execution
from app.models.workflow import Workflow
from app.services.analytics_service import invalidate_tenant_cache, _cache


# ---------------------------------------------------------------------------
# Helper: create workflow + executions directly in DB
# ---------------------------------------------------------------------------

async def _create_workflow(db_session, tenant_id: uuid.UUID, name: str = "Test Workflow") -> uuid.UUID:
    wf = Workflow(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name=name,
        description="test workflow",
        definition={"nodes": [], "edges": []},
    )
    db_session.add(wf)
    await db_session.commit()
    return wf.id


async def _create_execution(
    db_session,
    tenant_id: uuid.UUID,
    workflow_id: uuid.UUID,
    status: str = "completed",
    total_tokens: int = 1000,
    total_cost: float = 0.05,
    created_at: datetime | None = None,
    started_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> uuid.UUID:
    now = datetime.now(timezone.utc)
    ex = Execution(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        status=status,
        total_tokens=total_tokens,
        total_cost=total_cost,
        created_at=created_at or now,
        started_at=started_at or now,
        completed_at=completed_at or (now + timedelta(seconds=10)),
    )
    db_session.add(ex)
    await db_session.commit()
    return ex.id


# ---------------------------------------------------------------------------
# Fixture: registered user with tenant_id extracted
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def user_with_tenant(client: AsyncClient, registered_user: dict, db_session):
    """Return (auth_headers, tenant_id)."""
    headers = {"Authorization": f"Bearer {registered_user['access_token']}"}
    # RegisterResponse includes tenant_id directly
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    # Clear cache before each test
    _cache.clear()
    return headers, tenant_id


# ===================================================================
# Overview Tests
# ===================================================================

class TestOverview:
    """Tests for GET /api/v1/analytics/overview."""

    @pytest.mark.asyncio
    async def test_overview_empty(self, client, user_with_tenant):
        headers, _ = user_with_tenant
        resp = await client.get("/api/v1/analytics/overview", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_executions"] == 0
        assert data["successful"] == 0
        assert data["failed"] == 0
        assert data["tokens_used"] == 0
        assert data["total_cost"] == 0.0
        assert data["success_rate"] is None

    @pytest.mark.asyncio
    async def test_overview_with_data(self, client, user_with_tenant, db_session):
        headers, tenant_id = user_with_tenant
        wf_id = await _create_workflow(db_session, tenant_id)
        await _create_execution(db_session, tenant_id, wf_id, "completed", 500, 0.03)
        await _create_execution(db_session, tenant_id, wf_id, "completed", 700, 0.05)
        await _create_execution(db_session, tenant_id, wf_id, "failed", 200, 0.01)
        _cache.clear()

        resp = await client.get("/api/v1/analytics/overview", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_executions"] == 3
        assert data["successful"] == 2
        assert data["failed"] == 1
        assert data["tokens_used"] == 1400
        assert data["total_cost"] == pytest.approx(0.09, abs=0.001)
        assert data["success_rate"] == pytest.approx(66.7, abs=0.1)

    @pytest.mark.asyncio
    async def test_overview_week_period(self, client, user_with_tenant, db_session):
        headers, tenant_id = user_with_tenant
        wf_id = await _create_workflow(db_session, tenant_id)
        await _create_execution(db_session, tenant_id, wf_id, "completed", 100, 0.01)
        _cache.clear()

        resp = await client.get("/api/v1/analytics/overview?period=week", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_executions"] >= 1

    @pytest.mark.asyncio
    async def test_overview_invalid_period(self, client, user_with_tenant):
        headers, _ = user_with_tenant
        resp = await client.get("/api/v1/analytics/overview?period=invalid", headers=headers)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_overview_no_auth(self, client):
        resp = await client.get("/api/v1/analytics/overview")
        assert resp.status_code == 401


# ===================================================================
# Cost Timeline Tests
# ===================================================================

class TestCostTimeline:
    """Tests for GET /api/v1/analytics/cost-timeline."""

    @pytest.mark.asyncio
    async def test_timeline_empty(self, client, user_with_tenant):
        headers, _ = user_with_tenant
        resp = await client.get("/api/v1/analytics/cost-timeline", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        # Should have 30 days of zeros by default
        assert len(data) == 30
        for item in data:
            assert item["daily_cost"] == 0.0
            assert item["executions_count"] == 0

    @pytest.mark.asyncio
    async def test_timeline_with_data(self, client, user_with_tenant, db_session):
        headers, tenant_id = user_with_tenant
        wf_id = await _create_workflow(db_session, tenant_id)
        now = datetime.now(timezone.utc)
        await _create_execution(
            db_session, tenant_id, wf_id, "completed", 500, 0.05, created_at=now
        )
        await _create_execution(
            db_session, tenant_id, wf_id, "completed", 300, 0.03, created_at=now
        )
        _cache.clear()

        resp = await client.get("/api/v1/analytics/cost-timeline", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 30

        # Today should have data
        today_str = now.strftime("%Y-%m-%d")
        today_item = next((d for d in data if d["day"] == today_str), None)
        assert today_item is not None
        assert today_item["daily_cost"] == pytest.approx(0.08, abs=0.01)
        assert today_item["executions_count"] == 2

    @pytest.mark.asyncio
    async def test_timeline_fills_missing_days(self, client, user_with_tenant, db_session):
        headers, tenant_id = user_with_tenant
        wf_id = await _create_workflow(db_session, tenant_id)
        now = datetime.now(timezone.utc)
        # Create execution only for today
        await _create_execution(db_session, tenant_id, wf_id, "completed", 100, 0.01, created_at=now)
        _cache.clear()

        resp = await client.get("/api/v1/analytics/cost-timeline?days=7", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 7
        # Only today should have data, others should be 0
        non_zero = [d for d in data if d["daily_cost"] > 0]
        assert len(non_zero) == 1

    @pytest.mark.asyncio
    async def test_timeline_custom_days(self, client, user_with_tenant):
        headers, _ = user_with_tenant
        resp = await client.get("/api/v1/analytics/cost-timeline?days=7", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 7

    @pytest.mark.asyncio
    async def test_timeline_no_auth(self, client):
        resp = await client.get("/api/v1/analytics/cost-timeline")
        assert resp.status_code == 401


# ===================================================================
# Workflow Breakdown Tests
# ===================================================================

class TestWorkflowBreakdown:
    """Tests for GET /api/v1/analytics/workflow-breakdown."""

    @pytest.mark.asyncio
    async def test_breakdown_empty(self, client, user_with_tenant):
        headers, _ = user_with_tenant
        resp = await client.get("/api/v1/analytics/workflow-breakdown", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data == []

    @pytest.mark.asyncio
    async def test_breakdown_with_data(self, client, user_with_tenant, db_session):
        headers, tenant_id = user_with_tenant
        wf1_id = await _create_workflow(db_session, tenant_id, "Workflow A")
        wf2_id = await _create_workflow(db_session, tenant_id, "Workflow B")
        await _create_execution(db_session, tenant_id, wf1_id, "completed", 1000, 0.10)
        await _create_execution(db_session, tenant_id, wf1_id, "completed", 500, 0.05)
        await _create_execution(db_session, tenant_id, wf2_id, "completed", 200, 0.02)
        _cache.clear()

        resp = await client.get("/api/v1/analytics/workflow-breakdown", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2
        # Sorted by cost desc — Workflow A first
        assert data[0]["workflow_name"] == "Workflow A"
        assert data[0]["runs"] == 2
        assert data[0]["cost"] == pytest.approx(0.15, abs=0.01)
        assert data[1]["workflow_name"] == "Workflow B"
        assert data[1]["runs"] == 1
        assert data[1]["cost"] == pytest.approx(0.02, abs=0.01)

    @pytest.mark.asyncio
    async def test_breakdown_cost_percentage(self, client, user_with_tenant, db_session):
        headers, tenant_id = user_with_tenant
        wf1_id = await _create_workflow(db_session, tenant_id, "WF1")
        wf2_id = await _create_workflow(db_session, tenant_id, "WF2")
        await _create_execution(db_session, tenant_id, wf1_id, "completed", 1000, 0.75)
        await _create_execution(db_session, tenant_id, wf2_id, "completed", 200, 0.25)
        _cache.clear()

        resp = await client.get("/api/v1/analytics/workflow-breakdown", headers=headers)
        data = resp.json()
        assert data[0]["cost_percentage"] == pytest.approx(75.0, abs=0.1)
        assert data[1]["cost_percentage"] == pytest.approx(25.0, abs=0.1)

    @pytest.mark.asyncio
    async def test_breakdown_avg_duration(self, client, user_with_tenant, db_session):
        headers, tenant_id = user_with_tenant
        wf_id = await _create_workflow(db_session, tenant_id)
        now = datetime.now(timezone.utc)
        await _create_execution(
            db_session, tenant_id, wf_id, "completed", 500, 0.05,
            started_at=now, completed_at=now + timedelta(seconds=20),
        )
        await _create_execution(
            db_session, tenant_id, wf_id, "completed", 300, 0.03,
            started_at=now, completed_at=now + timedelta(seconds=40),
        )
        _cache.clear()

        resp = await client.get("/api/v1/analytics/workflow-breakdown", headers=headers)
        data = resp.json()
        assert len(data) == 1
        assert data[0]["avg_duration_sec"] == pytest.approx(30.0, abs=1.0)

    @pytest.mark.asyncio
    async def test_breakdown_no_auth(self, client):
        resp = await client.get("/api/v1/analytics/workflow-breakdown")
        assert resp.status_code == 401


# ===================================================================
# Export Tests
# ===================================================================

class TestExport:
    """Tests for GET /api/v1/analytics/export."""

    @pytest.mark.asyncio
    async def test_export_csv_empty(self, client, user_with_tenant):
        headers, _ = user_with_tenant
        resp = await client.get("/api/v1/analytics/export?format=csv", headers=headers)
        assert resp.status_code == 200
        assert "text/csv" in resp.headers.get("content-type", "")
        content = resp.text
        # Should contain header row
        assert "execution_id" in content
        assert "workflow_name" in content
        # Only header row, no data rows
        lines = [l for l in content.strip().split("\n") if l.strip()]
        assert len(lines) == 1

    @pytest.mark.asyncio
    async def test_export_csv_with_data(self, client, user_with_tenant, db_session):
        headers, tenant_id = user_with_tenant
        wf_id = await _create_workflow(db_session, tenant_id, "Export WF")
        await _create_execution(db_session, tenant_id, wf_id, "completed", 500, 0.05)
        await _create_execution(db_session, tenant_id, wf_id, "failed", 200, 0.02)

        resp = await client.get("/api/v1/analytics/export?format=csv", headers=headers)
        assert resp.status_code == 200
        content = resp.text
        lines = [l for l in content.strip().split("\n") if l.strip()]
        assert len(lines) == 3  # header + 2 data rows
        assert "Export WF" in content

    @pytest.mark.asyncio
    async def test_export_json(self, client, user_with_tenant, db_session):
        headers, tenant_id = user_with_tenant
        wf_id = await _create_workflow(db_session, tenant_id, "JSON WF")
        await _create_execution(db_session, tenant_id, wf_id, "completed", 500, 0.05)

        resp = await client.get("/api/v1/analytics/export?format=json", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["workflow_name"] == "JSON WF"
        assert data[0]["status"] == "completed"
        assert data[0]["tokens"] == 500

    @pytest.mark.asyncio
    async def test_export_json_empty(self, client, user_with_tenant):
        headers, _ = user_with_tenant
        resp = await client.get("/api/v1/analytics/export?format=json", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data == []

    @pytest.mark.asyncio
    async def test_export_date_filter(self, client, user_with_tenant, db_session):
        headers, tenant_id = user_with_tenant
        wf_id = await _create_workflow(db_session, tenant_id)
        now = datetime.now(timezone.utc)
        await _create_execution(db_session, tenant_id, wf_id, "completed", 100, 0.01, created_at=now)
        _cache.clear()

        # Filter from tomorrow — should get nothing
        tomorrow = (now + timedelta(days=1)).strftime("%Y-%m-%d")
        resp = await client.get(
            f"/api/v1/analytics/export?format=json&from={tomorrow}",
            headers=headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_export_invalid_format(self, client, user_with_tenant):
        headers, _ = user_with_tenant
        resp = await client.get("/api/v1/analytics/export?format=xml", headers=headers)
        assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_export_invalid_date_range(self, client, user_with_tenant):
        headers, _ = user_with_tenant
        resp = await client.get(
            "/api/v1/analytics/export?format=json&from=2026-04-20&to=2026-04-10",
            headers=headers,
        )
        assert resp.status_code == 400
        assert "from" in resp.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_export_no_auth(self, client):
        resp = await client.get("/api/v1/analytics/export")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_export_csv_content_disposition(self, client, user_with_tenant):
        headers, _ = user_with_tenant
        resp = await client.get("/api/v1/analytics/export?format=csv", headers=headers)
        assert "content-disposition" in resp.headers
        assert "executions_export.csv" in resp.headers["content-disposition"]


# ===================================================================
# Tenant Isolation Tests
# ===================================================================

class TestAnalyticsTenantIsolation:
    """Ensure analytics data is isolated per tenant."""

    @pytest.mark.asyncio
    async def test_overview_isolation(self, client, user_with_tenant, db_session):
        headers_a, tenant_a = user_with_tenant
        wf_a = await _create_workflow(db_session, tenant_a, "Tenant A WF")
        await _create_execution(db_session, tenant_a, wf_a, "completed", 1000, 0.10)
        _cache.clear()

        # Register second tenant
        resp = await client.post("/api/v1/auth/register", json={
            "email": "other@other.com",
            "password": "securepass123",
            "full_name": "Other Owner",
            "tenant_name": "Other Corp",
        })
        assert resp.status_code == 201
        headers_b = {"Authorization": f"Bearer {resp.json()['access_token']}"}

        # Tenant B should see empty overview
        resp_b = await client.get("/api/v1/analytics/overview", headers=headers_b)
        assert resp_b.status_code == 200
        assert resp_b.json()["total_executions"] == 0

        # Tenant A sees their data
        _cache.clear()
        resp_a = await client.get("/api/v1/analytics/overview", headers=headers_a)
        assert resp_a.status_code == 200
        assert resp_a.json()["total_executions"] == 1

    @pytest.mark.asyncio
    async def test_export_isolation(self, client, user_with_tenant, db_session):
        headers_a, tenant_a = user_with_tenant
        wf_a = await _create_workflow(db_session, tenant_a, "Tenant A WF")
        await _create_execution(db_session, tenant_a, wf_a, "completed", 500, 0.05)

        # Register second tenant
        resp = await client.post("/api/v1/auth/register", json={
            "email": "other2@other.com",
            "password": "securepass123",
            "full_name": "Other Owner 2",
            "tenant_name": "Other Corp 2",
        })
        headers_b = {"Authorization": f"Bearer {resp.json()['access_token']}"}

        # Tenant B export should be empty
        resp_b = await client.get("/api/v1/analytics/export?format=json", headers=headers_b)
        assert resp_b.status_code == 200
        assert resp_b.json() == []

    @pytest.mark.asyncio
    async def test_breakdown_isolation(self, client, user_with_tenant, db_session):
        headers_a, tenant_a = user_with_tenant
        wf_a = await _create_workflow(db_session, tenant_a, "Secret WF")
        await _create_execution(db_session, tenant_a, wf_a, "completed", 500, 0.05)
        _cache.clear()

        # Register second tenant
        resp = await client.post("/api/v1/auth/register", json={
            "email": "other3@other.com",
            "password": "securepass123",
            "full_name": "Other Owner 3",
            "tenant_name": "Other Corp 3",
        })
        headers_b = {"Authorization": f"Bearer {resp.json()['access_token']}"}

        resp_b = await client.get("/api/v1/analytics/workflow-breakdown", headers=headers_b)
        assert resp_b.status_code == 200
        assert resp_b.json() == []


# ===================================================================
# Cache Tests
# ===================================================================

class TestAnalyticsCache:
    """Basic cache behavior tests."""

    @pytest.mark.asyncio
    async def test_cache_invalidation(self, client, user_with_tenant, db_session):
        headers, tenant_id = user_with_tenant
        _cache.clear()

        # First call — empty
        resp1 = await client.get("/api/v1/analytics/overview", headers=headers)
        assert resp1.json()["total_executions"] == 0

        # Add execution
        wf_id = await _create_workflow(db_session, tenant_id)
        await _create_execution(db_session, tenant_id, wf_id, "completed", 500, 0.05)

        # Without invalidation, cache should still return old data
        resp2 = await client.get("/api/v1/analytics/overview", headers=headers)
        assert resp2.json()["total_executions"] == 0  # cached!

        # Invalidate and retry
        invalidate_tenant_cache(tenant_id)
        resp3 = await client.get("/api/v1/analytics/overview", headers=headers)
        assert resp3.json()["total_executions"] == 1
