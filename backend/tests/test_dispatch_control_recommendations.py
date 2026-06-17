"""Tests for M12 dispatch control automation recommendations."""

import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

from app.models.connector import WebhookEvent, WorkflowTrigger
from app.models.dispatch_alert import DispatchIncidentAcknowledgement
from app.models.execution import Execution
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
        name="Automation Recommendation WF",
        description="automation recommendation test",
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


async def _create_throttled_trigger(
    db_session,
    tenant_id: uuid.UUID,
    workflow_id: uuid.UUID,
) -> None:
    trigger = WorkflowTrigger(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        trigger_type="webhook",
        public_id=uuid.uuid4().hex,
        config={
            "rate_limit": {
                "enabled": True,
                "max_events": 1,
                "window_seconds": 3600,
            },
            "auth": "none",
        },
    )
    db_session.add(trigger)
    await db_session.commit()
    await db_session.refresh(trigger)

    db_session.add(
        WebhookEvent(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            workflow_id=workflow_id,
            trigger_id=trigger.id,
            payload={"token": "secret-webhook-payload"},
            headers_sanitized={"authorization": "Bearer ****"},
            status="received",
            created_at=datetime.now(timezone.utc),
        )
    )
    await db_session.commit()


async def _create_sla_breached_incident(
    db_session,
    tenant_id: uuid.UUID,
) -> None:
    created_at = datetime.now(timezone.utc) - timedelta(minutes=150)
    row = DispatchIncidentAcknowledgement(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        incident_key=f"dispatch:{uuid.uuid4().hex}",
        status="acknowledged",
        severity="critical",
        summary="Dispatch incident handoff required",
        alert_codes=["dead_lettered"],
        acknowledged_by_email="owner@test.com",
        acknowledged_by_name="Secret Owner",
        note="operator note token=secret-note-token",
        created_at=created_at,
        updated_at=created_at,
    )
    db_session.add(row)
    await db_session.commit()


@pytest.mark.asyncio
async def test_dispatch_control_recommendations_are_tenant_scoped_dry_run_without_secrets(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    workflow = await _create_workflow(db_session, tenant_id, dispatch_paused=True)
    await _create_dead_letter_execution(db_session, tenant_id, workflow.id)
    await _create_throttled_trigger(db_session, tenant_id, workflow.id)
    await _create_sla_breached_incident(db_session, tenant_id)

    other = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"recommendations-other-{uuid.uuid4()}@test.com",
            "password": "securepass123",
            "full_name": "Other Recommendations User",
            "tenant_name": "Other Recommendations Tenant",
        },
    )
    assert other.status_code == 201, other.text
    other_tenant_id = uuid.UUID(other.json()["tenant_id"])
    other_workflow = await _create_workflow(db_session, other_tenant_id, dispatch_paused=True)
    await _create_dead_letter_execution(db_session, other_tenant_id, other_workflow.id)

    before_execution_count = await db_session.scalar(select(func.count(Execution.id)))

    resp = await client.get(
        "/api/v1/analytics/dispatch-control-recommendations?window_hours=24&sla_minutes=60",
        headers=auth_headers,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["dry_run"] is True
    assert data["window_hours"] == 24
    assert data["sla_minutes"] == 60

    codes = {item["code"] for item in data["recommendations"]}
    assert "auto_retry_dead_letters" in codes
    assert "auto_resume_guard" in codes
    assert "auto_rate_limit_tuning" in codes
    assert "auto_sla_escalation" in codes
    assert "setup_alert_routing" in codes
    assert data["recommendation_count"] == len(data["recommendations"])
    assert data["automation_ready_count"] >= 1

    dead_letter = next(item for item in data["recommendations"] if item["code"] == "auto_retry_dead_letters")
    assert dead_letter["priority"] == "critical"
    assert "1 dead-lettered" in " ".join(dead_letter["evidence"])

    serialized = str(data)
    assert "secret-workflow-token" not in serialized
    assert "secret-webhook-header" not in serialized
    assert "secret-webhook-payload" not in serialized
    assert "secret-note-token" not in serialized
    assert "owner@test.com" not in serialized
    assert "Other Recommendations Tenant" not in serialized

    await db_session.refresh(workflow)
    after_execution_count = await db_session.scalar(select(func.count(Execution.id)))
    assert workflow.dispatch_paused is True
    assert after_execution_count == before_execution_count


@pytest.mark.asyncio
async def test_dispatch_control_recommendations_validate_query_and_auth(
    client,
    auth_headers,
):
    no_auth = await client.get("/api/v1/analytics/dispatch-control-recommendations")
    assert no_auth.status_code == 401

    invalid_window = await client.get(
        "/api/v1/analytics/dispatch-control-recommendations?window_hours=0",
        headers=auth_headers,
    )
    assert invalid_window.status_code == 422

    invalid_sla = await client.get(
        "/api/v1/analytics/dispatch-control-recommendations?sla_minutes=0",
        headers=auth_headers,
    )
    assert invalid_sla.status_code == 422
