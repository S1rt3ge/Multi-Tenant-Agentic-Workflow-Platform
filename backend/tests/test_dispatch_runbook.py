"""Tests for M12 dispatch runbook export and incident handoff."""

import uuid

from sqlalchemy import select

from app.models.dispatch_alert import DispatchAlertDelivery
from app.models.execution import Execution
from app.models.workflow import Workflow


async def _create_workflow(db_session, tenant_id: uuid.UUID) -> Workflow:
    workflow = Workflow(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="Dispatch Runbook WF",
        description="dispatch runbook test",
        definition={
            "nodes": [{"id": "secret-node", "data": {"token": "secret-workflow-token"}}],
            "edges": [],
        },
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


async def _configure_runbook_policy(client, auth_headers: dict) -> dict:
    channel_resp = await client.post(
        "/api/v1/analytics/dispatch-alert-channels",
        json={
            "name": "Runbook webhook",
            "channel_type": "webhook",
            "config": {
                "url": "https://8.8.8.8/dispatch",
                "headers": {"Authorization": "Bearer secret-runbook-token"},
            },
        },
        headers=auth_headers,
    )
    assert channel_resp.status_code == 201, channel_resp.text
    channel = channel_resp.json()

    policy_resp = await client.put(
        "/api/v1/analytics/dispatch-alert-policy",
        json={
            "enabled": True,
            "channels": [
                {
                    "type": "webhook",
                    "target": "Runbook webhook",
                    "credential_id": channel["id"],
                    "enabled": True,
                }
            ],
            "severities": ["critical", "warning"],
            "alert_codes": ["dead_lettered", "dispatch_paused"],
            "cooldown_minutes": 30,
        },
        headers=auth_headers,
    )
    assert policy_resp.status_code == 200, policy_resp.text
    return channel


async def _prepare_incident(client, auth_headers, registered_user, db_session) -> uuid.UUID:
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    workflow = await _create_workflow(db_session, tenant_id)
    await _create_dead_letter_execution(db_session, tenant_id, workflow.id)
    channel = await _configure_runbook_policy(client, auth_headers)
    db_session.add(
        DispatchAlertDelivery(
            tenant_id=tenant_id,
            channel_id=uuid.UUID(channel["id"]),
            alert_code="dead_lettered",
            channel_type="webhook",
            target_preview="https://8.8.8.8/dispatch?token=secret-runbook-token",
            status="failed",
            status_code=500,
            error_message="Authorization: Bearer secret-runbook-token",
        )
    )
    await db_session.commit()
    return tenant_id


async def test_dispatch_runbook_requires_auth(client):
    resp = await client.get("/api/v1/analytics/dispatch-runbook")

    assert resp.status_code == 401


async def test_dispatch_runbook_returns_sanitized_incident_handoff(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    tenant_id = await _prepare_incident(client, auth_headers, registered_user, db_session)

    resp = await client.get(
        "/api/v1/analytics/dispatch-runbook",
        headers=auth_headers,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["tenant_id"] == str(tenant_id)
    assert data["severity"] == "critical"
    assert data["summary"] == "Dispatch incident handoff required"
    assert data["policy"]["enabled"] is True
    assert data["policy"]["configured_channels"] == 1
    assert data["health"]["dead_lettered_executions"] == 1
    assert data["alerts"][0]["code"] == "dead_lettered"
    assert data["recent_deliveries"][0]["target_preview"].endswith("token=****")
    assert data["recent_deliveries"][0]["error_message"].startswith("Authorization:")
    assert any("dead-letter" in action["title"].lower() for action in data["recommended_actions"])
    assert "secret-runbook-token" not in str(data)
    assert "secret-webhook-header" not in str(data)
    assert "secret-workflow-token" not in str(data)
    assert "secret-lead" not in str(data)

    other = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"dispatch-runbook-other-{uuid.uuid4()}@test.com",
            "password": "securepass123",
            "full_name": "Other Runbook User",
            "tenant_name": "Other Runbook Tenant",
        },
    )
    assert other.status_code == 201, other.text
    other_resp = await client.get(
        "/api/v1/analytics/dispatch-runbook",
        headers={"Authorization": f"Bearer {other.json()['access_token']}"},
    )
    assert other_resp.status_code == 200, other_resp.text
    assert other_resp.json()["health"]["dead_lettered_executions"] == 0


async def test_dispatch_runbook_quiet_state_is_low_severity(client, auth_headers):
    resp = await client.get(
        "/api/v1/analytics/dispatch-runbook",
        headers=auth_headers,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["severity"] == "info"
    assert data["summary"] == "No active dispatch incident"
    assert data["alerts"] == []
    assert data["recent_deliveries"] == []
    assert data["recommended_actions"][0]["title"] == "Continue monitoring dispatch health"


async def test_dispatch_runbook_markdown_export_is_sanitized(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    await _prepare_incident(client, auth_headers, registered_user, db_session)

    resp = await client.get(
        "/api/v1/analytics/dispatch-runbook?format=markdown",
        headers=auth_headers,
    )

    assert resp.status_code == 200, resp.text
    assert "attachment; filename=dispatch_runbook.md" in resp.headers["content-disposition"]
    assert resp.headers["content-type"].startswith("text/markdown")
    text = resp.text
    assert "# Dispatch Incident Runbook" in text
    assert "Dead-letter queue needs review" in text
    assert "secret-runbook-token" not in text
    assert "secret-webhook-header" not in text
    assert "secret-workflow-token" not in text
    assert "secret-lead" not in text


async def test_dispatch_runbook_does_not_mutate_delivery_audit(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    tenant_id = await _prepare_incident(client, auth_headers, registered_user, db_session)
    before = await db_session.scalar(
        select(DispatchAlertDelivery).where(DispatchAlertDelivery.tenant_id == tenant_id)
    )
    assert before is not None

    resp = await client.get(
        "/api/v1/analytics/dispatch-runbook",
        headers=auth_headers,
    )

    assert resp.status_code == 200, resp.text
    rows = (
        await db_session.execute(
            select(DispatchAlertDelivery).where(DispatchAlertDelivery.tenant_id == tenant_id)
        )
    ).scalars().all()
    assert len(rows) == 1
