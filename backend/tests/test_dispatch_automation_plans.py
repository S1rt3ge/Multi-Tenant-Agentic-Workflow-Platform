"""Tests for M12 approval-gated dispatch automation plans."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.core.security import create_access_token
from app.models.dispatch_alert import DispatchAutomationPlan, DispatchAutomationWorkerRun
from app.models.execution import Execution
from app.models.tenant import Tenant
from app.models.user import User
from app.models.workflow import Workflow


async def _create_workflow(
    db_session,
    tenant_id: uuid.UUID,
    *,
    dispatch_paused: bool = False,
) -> Workflow:
    workflow = Workflow(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="Automation Plan WF",
        description="automation plan test",
        definition={"nodes": [{"id": "secret-node", "data": {"token": "secret-workflow-token"}}]},
        dispatch_paused=dispatch_paused,
    )
    db_session.add(workflow)
    await db_session.commit()
    await db_session.refresh(workflow)
    return workflow


async def _create_dead_letter_execution(
    db_session,
    tenant_id: uuid.UUID,
    workflow_id: uuid.UUID,
) -> None:
    db_session.add(
        Execution(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            status="failed",
            input_data={
                "trigger": {"type": "webhook"},
                "payload": {"lead_id": "secret-lead"},
                "headers": {"x-webhook-secret": "secret-webhook-header"},
                "dispatch": {"dead_lettered": True},
            },
        )
    )
    await db_session.commit()


async def _prepare_retry_recommendation(registered_user, db_session) -> tuple[uuid.UUID, Workflow]:
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    workflow = await _create_workflow(db_session, tenant_id, dispatch_paused=True)
    await _create_dead_letter_execution(db_session, tenant_id, workflow.id)
    return tenant_id, workflow


async def _viewer_headers(client, auth_headers: dict, db_session, role: str = "viewer") -> dict:
    invite = await client.post(
        "/api/v1/tenants/invite",
        json={"email": f"automation-plan-{role}-{uuid.uuid4()}@test.com", "role": role},
        headers=auth_headers,
    )
    assert invite.status_code == 201, invite.text
    invited = invite.json()
    invited_user = await db_session.get(User, uuid.UUID(invited["id"]))
    invited_user.must_change_password = False
    await db_session.commit()
    token = create_access_token(
        user_id=uuid.UUID(invited["id"]),
        tenant_id=uuid.UUID(invited["tenant_id"]),
        role=role,
    )
    return {"Authorization": f"Bearer {token}"}


async def _platform_admin_headers(db_session, tenant_id: uuid.UUID) -> dict:
    user = User(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        email=f"platform-admin-{uuid.uuid4()}@test.com",
        password_hash="unused-platform-admin-test-hash",
        full_name="Platform Admin",
        role="platform_admin",
        must_change_password=False,
    )
    db_session.add(user)
    await db_session.commit()
    token = create_access_token(
        user_id=user.id,
        tenant_id=tenant_id,
        role="platform_admin",
    )
    return {"Authorization": f"Bearer {token}"}


async def _create_plan(client, headers: dict, recommendation_code: str = "auto_retry_dead_letters"):
    resp = await client.post(
        "/api/v1/analytics/dispatch-automation-plans",
        json={"recommendation_code": recommendation_code},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.mark.asyncio
async def test_owner_can_create_pending_plan_from_current_recommendation_without_mutation(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    tenant_id, workflow = await _prepare_retry_recommendation(registered_user, db_session)
    before_execution_count = await db_session.scalar(select(func.count(Execution.id)))

    resp = await client.post(
        "/api/v1/analytics/dispatch-automation-plans",
        json={"recommendation_code": "auto_retry_dead_letters"},
        headers=auth_headers,
    )

    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["tenant_id"] == str(tenant_id)
    assert data["recommendation_code"] == "auto_retry_dead_letters"
    assert data["status"] == "pending_approval"
    assert data["dry_run"] is True
    assert data["automation_type"] == "approval_gated_retry"
    assert data["requested_by_email"] == registered_user["email"]
    assert data["approved_by_email"] is None
    assert data["rejected_by_email"] is None
    assert "1 dead-lettered" in " ".join(data["evidence"])

    serialized = str(data)
    assert "secret-workflow-token" not in serialized
    assert "secret-webhook-header" not in serialized
    assert "secret-lead" not in serialized

    duplicate = await client.post(
        "/api/v1/analytics/dispatch-automation-plans",
        json={"recommendation_code": "auto_retry_dead_letters"},
        headers=auth_headers,
    )
    assert duplicate.status_code == 409

    stale = await client.post(
        "/api/v1/analytics/dispatch-automation-plans",
        json={"recommendation_code": "not_current"},
        headers=auth_headers,
    )
    assert stale.status_code == 409

    await db_session.refresh(workflow)
    after_execution_count = await db_session.scalar(select(func.count(Execution.id)))
    assert workflow.dispatch_paused is True
    assert after_execution_count == before_execution_count


@pytest.mark.asyncio
async def test_plan_list_is_tenant_scoped_and_viewer_cannot_create(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    tenant_id, _workflow = await _prepare_retry_recommendation(registered_user, db_session)
    plan = await _create_plan(client, auth_headers)

    viewer_headers = await _viewer_headers(client, auth_headers, db_session)
    forbidden = await client.post(
        "/api/v1/analytics/dispatch-automation-plans",
        json={"recommendation_code": "auto_retry_dead_letters"},
        headers=viewer_headers,
    )
    assert forbidden.status_code == 403

    plans = await client.get("/api/v1/analytics/dispatch-automation-plans", headers=auth_headers)
    assert plans.status_code == 200, plans.text
    assert [item["id"] for item in plans.json()["items"]] == [plan["id"]]
    assert plans.json()["items"][0]["tenant_id"] == str(tenant_id)

    other = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"automation-plan-other-{uuid.uuid4()}@test.com",
            "password": "securepass123",
            "full_name": "Other Automation Plan User",
            "tenant_name": "Other Automation Plan Tenant",
        },
    )
    assert other.status_code == 201, other.text
    other_plans = await client.get(
        "/api/v1/analytics/dispatch-automation-plans",
        headers={"Authorization": f"Bearer {other.json()['access_token']}"},
    )
    assert other_plans.status_code == 200, other_plans.text
    assert other_plans.json()["items"] == []


@pytest.mark.asyncio
async def test_owner_approves_and_rejects_pending_plans_only(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    await _prepare_retry_recommendation(registered_user, db_session)
    editor_headers = await _viewer_headers(client, auth_headers, db_session, role="editor")
    plan = await _create_plan(client, auth_headers)

    editor_approve = await client.post(
        f"/api/v1/analytics/dispatch-automation-plans/{plan['id']}/approve",
        headers=editor_headers,
    )
    assert editor_approve.status_code == 403

    approved = await client.post(
        f"/api/v1/analytics/dispatch-automation-plans/{plan['id']}/approve",
        headers=auth_headers,
    )
    assert approved.status_code == 200, approved.text
    approved_data = approved.json()
    assert approved_data["status"] == "approved"
    assert approved_data["approved_by_email"] == registered_user["email"]
    assert approved_data["approved_at"] is not None

    approve_again = await client.post(
        f"/api/v1/analytics/dispatch-automation-plans/{plan['id']}/approve",
        headers=auth_headers,
    )
    assert approve_again.status_code == 409

    routing_plan = await _create_plan(client, auth_headers, "setup_alert_routing")
    rejected = await client.post(
        f"/api/v1/analytics/dispatch-automation-plans/{routing_plan['id']}/reject",
        json={"rejection_note": "blocked by token=secret-rejection-token"},
        headers=auth_headers,
    )
    assert rejected.status_code == 200, rejected.text
    rejected_data = rejected.json()
    assert rejected_data["status"] == "rejected"
    assert rejected_data["rejected_by_email"] == registered_user["email"]
    assert rejected_data["rejected_at"] is not None
    assert "secret-rejection-token" not in str(rejected_data)

    stored_plan = await db_session.get(DispatchAutomationPlan, uuid.UUID(routing_plan["id"]))
    assert stored_plan.rejection_note.endswith("token=****")

    reject_again = await client.post(
        f"/api/v1/analytics/dispatch-automation-plans/{routing_plan['id']}/reject",
        json={"rejection_note": "already rejected"},
        headers=auth_headers,
    )
    assert reject_again.status_code == 409


@pytest.mark.asyncio
async def test_owner_can_run_approved_automation_worker_once_with_sanitized_counts(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    workflow = await _create_workflow(db_session, tenant_id, dispatch_paused=True)
    plan = await _create_plan(client, auth_headers, "auto_resume_guard")
    approved = await client.post(
        f"/api/v1/analytics/dispatch-automation-plans/{plan['id']}/approve",
        headers=auth_headers,
    )
    assert approved.status_code == 200, approved.text

    resp = await client.post(
        "/api/v1/analytics/dispatch-automation-worker/run?limit=5",
        headers=auth_headers,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["run_id"] is not None
    assert data["claimed"] == 1
    assert data["executed"] == 1
    assert data["blocked"] == 0
    assert data["failed"] == 0
    serialized = str(data)
    assert "secret-workflow-token" not in serialized
    assert "secret-webhook-header" not in serialized
    assert registered_user["email"] not in serialized

    await db_session.refresh(workflow)
    stored_plan = await db_session.get(DispatchAutomationPlan, uuid.UUID(plan["id"]))
    assert workflow.dispatch_paused is False
    assert stored_plan.status == "executed"
    assert stored_plan.execution_result["resumed_workflows"] == 1
    assert stored_plan.tenant_id == tenant_id

    stored_run = await db_session.get(DispatchAutomationWorkerRun, uuid.UUID(data["run_id"]))
    assert stored_run is not None
    assert stored_run.tenant_id == tenant_id
    assert stored_run.trigger_type == "manual"
    assert stored_run.status == "completed"
    assert stored_run.limit == 5
    assert stored_run.claimed == 1
    assert stored_run.executed == 1
    assert stored_run.blocked == 0
    assert stored_run.failed == 0

    runs = await client.get("/api/v1/analytics/dispatch-automation-worker/runs", headers=auth_headers)
    assert runs.status_code == 200, runs.text
    run_items = runs.json()["items"]
    assert [item["id"] for item in run_items] == [data["run_id"]]
    assert run_items[0]["trigger_type"] == "manual"
    assert run_items[0]["status"] == "completed"
    assert run_items[0]["claimed"] == 1
    assert run_items[0]["executed"] == 1
    assert run_items[0]["error_message"] is None
    assert registered_user["email"] not in str(runs.json())
    assert "secret-workflow-token" not in str(runs.json())


@pytest.mark.asyncio
async def test_manual_automation_worker_run_is_owner_only_and_validates_limit(
    client,
    auth_headers,
    db_session,
):
    editor_headers = await _viewer_headers(client, auth_headers, db_session, role="editor")
    viewer_headers = await _viewer_headers(client, auth_headers, db_session, role="viewer")

    editor = await client.post(
        "/api/v1/analytics/dispatch-automation-worker/run",
        headers=editor_headers,
    )
    viewer = await client.post(
        "/api/v1/analytics/dispatch-automation-worker/run",
        headers=viewer_headers,
    )
    invalid = await client.post(
        "/api/v1/analytics/dispatch-automation-worker/run?limit=0",
        headers=auth_headers,
    )

    assert editor.status_code == 403
    assert viewer.status_code == 403
    assert invalid.status_code == 422


@pytest.mark.asyncio
async def test_automation_worker_schedule_config_is_owner_gated_and_validated(
    client,
    auth_headers,
    db_session,
):
    default_resp = await client.get(
        "/api/v1/analytics/dispatch-automation-worker/config",
        headers=auth_headers,
    )
    assert default_resp.status_code == 200, default_resp.text
    assert default_resp.json() == {
        "enabled": False,
        "interval_minutes": 15,
        "max_plans_per_run": 10,
    }

    updated_resp = await client.put(
        "/api/v1/analytics/dispatch-automation-worker/config",
        json={"enabled": True, "interval_minutes": 30, "max_plans_per_run": 25},
        headers=auth_headers,
    )
    assert updated_resp.status_code == 200, updated_resp.text
    assert updated_resp.json() == {
        "enabled": True,
        "interval_minutes": 30,
        "max_plans_per_run": 25,
    }

    reread = await client.get(
        "/api/v1/analytics/dispatch-automation-worker/config",
        headers=auth_headers,
    )
    assert reread.status_code == 200, reread.text
    assert reread.json() == updated_resp.json()

    editor_headers = await _viewer_headers(client, auth_headers, db_session, role="editor")
    viewer_headers = await _viewer_headers(client, auth_headers, db_session, role="viewer")
    editor_update = await client.put(
        "/api/v1/analytics/dispatch-automation-worker/config",
        json={"enabled": False, "interval_minutes": 15, "max_plans_per_run": 10},
        headers=editor_headers,
    )
    viewer_update = await client.put(
        "/api/v1/analytics/dispatch-automation-worker/config",
        json={"enabled": False, "interval_minutes": 15, "max_plans_per_run": 10},
        headers=viewer_headers,
    )
    invalid_interval = await client.put(
        "/api/v1/analytics/dispatch-automation-worker/config",
        json={"enabled": True, "interval_minutes": 4, "max_plans_per_run": 10},
        headers=auth_headers,
    )
    invalid_limit = await client.put(
        "/api/v1/analytics/dispatch-automation-worker/config",
        json={"enabled": True, "interval_minutes": 15, "max_plans_per_run": 51},
        headers=auth_headers,
    )

    assert editor_update.status_code == 403
    assert viewer_update.status_code == 403
    assert invalid_interval.status_code == 422
    assert invalid_limit.status_code == 422


@pytest.mark.asyncio
async def test_automation_worker_run_audit_is_tenant_scoped(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    db_session.add(
        DispatchAutomationWorkerRun(
            tenant_id=tenant_id,
            trigger_type="manual",
            status="completed",
            limit=10,
            claimed=2,
            executed=1,
            blocked=1,
            failed=0,
        )
    )
    await db_session.commit()

    own = await client.get(
        "/api/v1/analytics/dispatch-automation-worker/runs",
        headers=auth_headers,
    )
    assert own.status_code == 200, own.text
    assert len(own.json()["items"]) == 1
    assert own.json()["items"][0]["claimed"] == 2
    assert "triggered_by" not in own.json()["items"][0]
    assert registered_user["email"] not in str(own.json())

    other = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"automation-run-other-{uuid.uuid4()}@test.com",
            "password": "securepass123",
            "full_name": "Other Automation Run User",
            "tenant_name": "Other Automation Run Tenant",
        },
    )
    assert other.status_code == 201, other.text
    other_runs = await client.get(
        "/api/v1/analytics/dispatch-automation-worker/runs",
        headers={"Authorization": f"Bearer {other.json()['access_token']}"},
    )
    assert other_runs.status_code == 200, other_runs.text
    assert other_runs.json()["items"] == []


@pytest.mark.asyncio
async def test_owner_can_read_scheduler_diagnostics_without_mutation(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    workflow = await _create_workflow(db_session, tenant_id, dispatch_paused=True)
    plan = await _create_plan(client, auth_headers, "auto_resume_guard")
    approved = await client.post(
        f"/api/v1/analytics/dispatch-automation-plans/{plan['id']}/approve",
        headers=auth_headers,
    )
    assert approved.status_code == 200, approved.text
    config = await client.put(
        "/api/v1/analytics/dispatch-automation-worker/config",
        json={"enabled": True, "interval_minutes": 15, "max_plans_per_run": 7},
        headers=auth_headers,
    )
    assert config.status_code == 200, config.text

    resp = await client.get(
        "/api/v1/analytics/dispatch-automation-worker/diagnostics",
        headers=auth_headers,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["scheduler_enabled"] is False
    assert data["scheduler_interval_seconds"] == 60.0
    assert data["scheduler_tenant_limit"] == 25
    assert data["tenant_config"] == {
        "enabled": True,
        "interval_minutes": 15,
        "max_plans_per_run": 7,
    }
    assert data["approved_plan_count"] == 1
    assert data["latest_scheduled_run"] is None
    assert data["tenant_due_now"] is True
    assert data["tenant_skip_reason"] is None
    assert data["next_run_at"] is None
    assert data["backoff_until"] is None
    assert data["generated_at"] is not None

    serialized = str(data)
    assert registered_user["email"] not in serialized
    assert "secret-workflow-token" not in serialized
    assert "secret-webhook-header" not in serialized

    await db_session.refresh(workflow)
    stored_plan = await db_session.get(DispatchAutomationPlan, uuid.UUID(plan["id"]))
    runs = (
        await db_session.execute(
            select(DispatchAutomationWorkerRun).where(
                DispatchAutomationWorkerRun.tenant_id == tenant_id
            )
        )
    ).scalars().all()
    assert workflow.dispatch_paused is True
    assert stored_plan.status == "approved"
    assert runs == []


@pytest.mark.asyncio
async def test_scheduler_diagnostics_is_owner_only(client, auth_headers, db_session):
    editor_headers = await _viewer_headers(client, auth_headers, db_session, role="editor")
    viewer_headers = await _viewer_headers(client, auth_headers, db_session, role="viewer")

    editor = await client.get(
        "/api/v1/analytics/dispatch-automation-worker/diagnostics",
        headers=editor_headers,
    )
    viewer = await client.get(
        "/api/v1/analytics/dispatch-automation-worker/diagnostics",
        headers=viewer_headers,
    )

    assert editor.status_code == 403
    assert viewer.status_code == 403


@pytest.mark.asyncio
async def test_scheduler_diagnostics_reports_backoff_state_without_secrets(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    config = await client.put(
        "/api/v1/analytics/dispatch-automation-worker/config",
        json={"enabled": True, "interval_minutes": 5, "max_plans_per_run": 10},
        headers=auth_headers,
    )
    assert config.status_code == 200, config.text
    db_session.add(
        DispatchAutomationWorkerRun(
            tenant_id=tenant_id,
            trigger_type="scheduled",
            status="failed",
            limit=10,
            claimed=0,
            executed=0,
            blocked=0,
            failed=1,
            error_message="Authorization: Bearer secret-diagnostics-token",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
    )
    await db_session.commit()

    resp = await client.get(
        "/api/v1/analytics/dispatch-automation-worker/diagnostics",
        headers=auth_headers,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["tenant_due_now"] is False
    assert data["tenant_skip_reason"] == "backoff"
    assert data["next_run_at"] is not None
    assert data["backoff_until"] == data["next_run_at"]
    assert data["latest_scheduled_run"]["status"] == "failed"
    assert data["latest_scheduled_run"]["failed"] == 1
    assert "triggered_by" not in data["latest_scheduled_run"]
    assert "secret-diagnostics-token" not in str(data)
    assert data["latest_scheduled_run"]["error_message"] == "Authorization: **** ****"


@pytest.mark.asyncio
async def test_platform_admin_can_read_scheduler_fleet_without_mutation_or_secrets(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    workflow = await _create_workflow(db_session, tenant_id, dispatch_paused=True)
    plan = await _create_plan(client, auth_headers, "auto_resume_guard")
    approved = await client.post(
        f"/api/v1/analytics/dispatch-automation-plans/{plan['id']}/approve",
        headers=auth_headers,
    )
    assert approved.status_code == 200, approved.text
    config = await client.put(
        "/api/v1/analytics/dispatch-automation-worker/config",
        json={"enabled": True, "interval_minutes": 15, "max_plans_per_run": 6},
        headers=auth_headers,
    )
    assert config.status_code == 200, config.text

    other_tenant = Tenant(
        id=uuid.uuid4(),
        name="Secret Fleet Tenant Name",
        slug=f"secret-fleet-tenant-{uuid.uuid4()}",
        dispatch_automation_worker_config={
            "enabled": True,
            "interval_minutes": 5,
            "max_plans_per_run": 4,
        },
    )
    db_session.add(other_tenant)
    await db_session.commit()
    other_workflow = await _create_workflow(db_session, other_tenant.id, dispatch_paused=True)
    other_plan = DispatchAutomationPlan(
        id=uuid.uuid4(),
        tenant_id=other_tenant.id,
        recommendation_code="auto_resume_guard",
        automation_type="resume_guard",
        status="approved",
        priority="warning",
        title="Resume dispatch safely",
        rationale="Paused dispatch should be resumed after health checks pass.",
        suggested_action="Resume paused workflow dispatch.",
        confidence=0.82,
        evidence=["1 paused workflow"],
        blocked_by=[],
        requested_by_email="other-owner@test.com",
        approved_by_email="other-owner@test.com",
        approved_at=datetime.now(timezone.utc),
    )
    db_session.add_all(
        [
            other_plan,
            DispatchAutomationWorkerRun(
                tenant_id=other_tenant.id,
                trigger_type="scheduled",
                status="failed",
                limit=4,
                claimed=0,
                executed=0,
                blocked=0,
                failed=1,
                error_message="Authorization: Bearer secret-fleet-api-token",
                created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
            ),
        ]
    )
    await db_session.commit()
    audit_rows_before = await db_session.scalar(
        select(func.count(DispatchAutomationWorkerRun.id))
    )
    platform_admin_headers = await _platform_admin_headers(db_session, tenant_id)

    resp = await client.get(
        "/api/v1/analytics/dispatch-automation-worker/fleet",
        headers=platform_admin_headers,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["scheduler_enabled"] is False
    assert data["scheduler_interval_seconds"] == 60.0
    assert data["scheduler_tenant_limit"] == 25
    assert data["total_tenants"] >= 2
    assert data["enabled_tenants"] >= 2
    assert data["approved_plan_backlog"] >= 2
    assert len(data["tenants"]) >= 2
    summaries = {item["tenant_id"]: item for item in data["tenants"]}
    assert summaries[str(tenant_id)]["enabled"] is True
    assert summaries[str(tenant_id)]["due_now"] is True
    assert summaries[str(tenant_id)]["max_plans_per_run"] == 6
    assert summaries[str(other_tenant.id)]["skip_reason"] == "backoff"
    assert summaries[str(other_tenant.id)]["latest_scheduled_status"] == "failed"
    assert summaries[str(other_tenant.id)]["backoff_until"] is not None

    serialized = str(data)
    assert "Secret Fleet Tenant Name" not in serialized
    assert "secret-fleet-tenant" not in serialized
    assert registered_user["email"] not in serialized
    assert "other-owner@test.com" not in serialized
    assert "secret-workflow-token" not in serialized
    assert "secret-fleet-api-token" not in serialized
    assert "Authorization" not in serialized
    assert "error_message" not in serialized

    audit_rows_after = await db_session.scalar(
        select(func.count(DispatchAutomationWorkerRun.id))
    )
    assert audit_rows_after == audit_rows_before
    await db_session.refresh(workflow)
    await db_session.refresh(other_workflow)
    stored_plan = await db_session.get(DispatchAutomationPlan, uuid.UUID(plan["id"]))
    await db_session.refresh(other_plan)
    assert workflow.dispatch_paused is True
    assert other_workflow.dispatch_paused is True
    assert stored_plan.status == "approved"
    assert other_plan.status == "approved"


@pytest.mark.asyncio
async def test_scheduler_fleet_api_requires_platform_admin(
    client,
    auth_headers,
    db_session,
):
    editor_headers = await _viewer_headers(client, auth_headers, db_session, role="editor")
    viewer_headers = await _viewer_headers(client, auth_headers, db_session, role="viewer")

    owner = await client.get(
        "/api/v1/analytics/dispatch-automation-worker/fleet",
        headers=auth_headers,
    )
    editor = await client.get(
        "/api/v1/analytics/dispatch-automation-worker/fleet",
        headers=editor_headers,
    )
    viewer = await client.get(
        "/api/v1/analytics/dispatch-automation-worker/fleet",
        headers=viewer_headers,
    )
    no_auth = await client.get("/api/v1/analytics/dispatch-automation-worker/fleet")

    assert owner.status_code == 403
    assert editor.status_code == 403
    assert viewer.status_code == 403
    assert no_auth.status_code == 401

    invite = await client.post(
        "/api/v1/tenants/invite",
        json={"email": f"platform-admin-invite-{uuid.uuid4()}@test.com", "role": "platform_admin"},
        headers=auth_headers,
    )
    assert invite.status_code == 422


@pytest.mark.asyncio
async def test_scheduler_fleet_api_can_return_aggregate_only(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    config = await client.put(
        "/api/v1/analytics/dispatch-automation-worker/config",
        json={"enabled": True, "interval_minutes": 15, "max_plans_per_run": 6},
        headers=auth_headers,
    )
    assert config.status_code == 200, config.text
    platform_admin_headers = await _platform_admin_headers(db_session, tenant_id)

    resp = await client.get(
        "/api/v1/analytics/dispatch-automation-worker/fleet?include_tenants=false",
        headers=platform_admin_headers,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_tenants"] >= 1
    assert data["enabled_tenants"] >= 1
    assert data["tenants"] == []


@pytest.mark.asyncio
async def test_automation_plan_query_validation_and_auth(client, auth_headers):
    no_auth = await client.get("/api/v1/analytics/dispatch-automation-plans")
    assert no_auth.status_code == 401

    invalid_limit = await client.get(
        "/api/v1/analytics/dispatch-automation-plans?limit=0",
        headers=auth_headers,
    )
    assert invalid_limit.status_code == 422
