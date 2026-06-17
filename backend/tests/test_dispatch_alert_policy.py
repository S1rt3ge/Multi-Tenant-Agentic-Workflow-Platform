"""Tests for M12 dispatch alert routing policy and dry-run preview."""

import uuid

from app.core.security import create_access_token
from app.models.execution import Execution
from app.models.workflow import Workflow


async def _create_workflow(db_session, tenant_id: uuid.UUID) -> Workflow:
    workflow = Workflow(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="Dispatch Alert Policy WF",
        description="dispatch alert policy test",
        definition={"nodes": [], "edges": []},
    )
    db_session.add(workflow)
    await db_session.commit()
    await db_session.refresh(workflow)
    return workflow


async def _create_dead_letter_execution(db_session, tenant_id: uuid.UUID, workflow_id: uuid.UUID):
    execution = Execution(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        status="failed",
        input_data={
            "trigger": {"type": "webhook"},
            "payload": {"lead_id": "secret-lead"},
            "headers": {"x-webhook-secret": "secret-webhook-header"},
            "dispatch": {
                "attempt": 3,
                "dead_lettered": True,
                "dead_letter_reason": "max_attempts_exhausted",
            },
        },
    )
    db_session.add(execution)
    await db_session.commit()
    return execution


async def _create_viewer_headers(client, auth_headers: dict) -> dict:
    invite = await client.post(
        "/api/v1/tenants/invite",
        json={"email": f"dispatch-policy-viewer-{uuid.uuid4()}@test.com", "role": "viewer"},
        headers=auth_headers,
    )
    assert invite.status_code == 201, invite.text
    viewer = invite.json()
    token = create_access_token(
        user_id=uuid.UUID(viewer["id"]),
        tenant_id=uuid.UUID(viewer["tenant_id"]),
        role="viewer",
    )
    return {"Authorization": f"Bearer {token}"}


def _policy_payload() -> dict:
    return {
        "enabled": True,
        "channels": [
            {
                "type": "email",
                "target": "ops@example.com",
                "enabled": True,
            }
        ],
        "severities": ["critical", "warning"],
        "alert_codes": ["dead_lettered", "trigger_throttled"],
        "cooldown_minutes": 15,
    }


async def test_dispatch_alert_policy_returns_safe_defaults(client, auth_headers):
    resp = await client.get("/api/v1/analytics/dispatch-alert-policy", headers=auth_headers)

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["enabled"] is False
    assert data["channels"] == []
    assert "critical" in data["severities"]
    assert "warning" in data["severities"]
    assert "dead_lettered" in data["alert_codes"]
    assert data["cooldown_minutes"] >= 5


async def test_owner_can_update_dispatch_alert_policy(client, auth_headers):
    resp = await client.put(
        "/api/v1/analytics/dispatch-alert-policy",
        json=_policy_payload(),
        headers=auth_headers,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["enabled"] is True
    assert data["channels"][0]["type"] == "email"
    assert data["channels"][0]["target"] == "ops@example.com"
    assert data["cooldown_minutes"] == 15

    persisted = await client.get(
        "/api/v1/analytics/dispatch-alert-policy",
        headers=auth_headers,
    )
    assert persisted.status_code == 200, persisted.text
    assert persisted.json() == data


async def test_viewer_cannot_update_dispatch_alert_policy(client, auth_headers):
    viewer_headers = await _create_viewer_headers(client, auth_headers)

    resp = await client.put(
        "/api/v1/analytics/dispatch-alert-policy",
        json=_policy_payload(),
        headers=viewer_headers,
    )

    assert resp.status_code == 403


async def test_dispatch_alert_policy_is_tenant_scoped(client, auth_headers):
    update = await client.put(
        "/api/v1/analytics/dispatch-alert-policy",
        json=_policy_payload(),
        headers=auth_headers,
    )
    assert update.status_code == 200, update.text

    other = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"dispatch-policy-other-{uuid.uuid4()}@test.com",
            "password": "securepass123",
            "full_name": "Other Policy User",
            "tenant_name": "Other Policy Tenant",
        },
    )
    assert other.status_code == 201, other.text
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}

    resp = await client.get("/api/v1/analytics/dispatch-alert-policy", headers=other_headers)

    assert resp.status_code == 200, resp.text
    assert resp.json()["enabled"] is False
    assert resp.json()["channels"] == []


async def test_dispatch_alert_policy_preview_returns_dry_run_routes(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    workflow = await _create_workflow(db_session, tenant_id)
    await _create_dead_letter_execution(db_session, tenant_id, workflow.id)

    update = await client.put(
        "/api/v1/analytics/dispatch-alert-policy",
        json=_policy_payload(),
        headers=auth_headers,
    )
    assert update.status_code == 200, update.text

    resp = await client.post(
        "/api/v1/analytics/dispatch-alert-policy/preview",
        headers=auth_headers,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["dry_run"] is True
    assert data["policy_enabled"] is True
    assert [alert["code"] for alert in data["alerts"]] == ["dead_lettered"]
    assert data["routes"] == [
        {
            "channel_type": "email",
            "target": "ops@example.com",
            "alert_codes": ["dead_lettered"],
        }
    ]

    serialized = str(data)
    assert "secret-lead" not in serialized
    assert "secret-webhook-header" not in serialized
