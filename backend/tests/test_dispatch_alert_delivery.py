"""Tests for M12 dispatch alert delivery adapters and audit logs."""

import uuid
from types import SimpleNamespace

from sqlalchemy import select

from app.core.security import create_access_token
from app.models.dispatch_alert import (
    DispatchAlertChannelCredential,
    DispatchAlertDelivery,
)
from app.models.execution import Execution
from app.models.workflow import Workflow


async def _create_workflow(db_session, tenant_id: uuid.UUID) -> Workflow:
    workflow = Workflow(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="Dispatch Alert Delivery WF",
        description="dispatch alert delivery test",
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
            "dispatch": {"dead_lettered": True},
        },
    )
    db_session.add(execution)
    await db_session.commit()


async def _create_viewer_headers(client, auth_headers: dict) -> dict:
    invite = await client.post(
        "/api/v1/tenants/invite",
        json={"email": f"dispatch-delivery-viewer-{uuid.uuid4()}@test.com", "role": "viewer"},
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


def _channel_payload(url: str = "https://8.8.8.8/dispatch") -> dict:
    return {
        "name": "Ops webhook",
        "channel_type": "webhook",
        "config": {
            "url": url,
            "headers": {
                "Authorization": "Bearer secret-delivery-token",
                "X-Team": "ops",
            },
        },
    }


async def test_owner_can_create_encrypted_webhook_channel(
    client,
    auth_headers,
    db_session,
):
    resp = await client.post(
        "/api/v1/analytics/dispatch-alert-channels",
        json=_channel_payload(),
        headers=auth_headers,
    )

    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["name"] == "Ops webhook"
    assert data["channel_type"] == "webhook"
    assert data["config_preview"]["url"] == "https://8.8.8.8/dispatch"
    assert data["config_preview"]["headers"]["Authorization"] == "****"
    assert "encrypted_config" not in data
    assert "secret-delivery-token" not in str(data)

    stored = await db_session.get(DispatchAlertChannelCredential, uuid.UUID(data["id"]))
    assert stored is not None
    assert "secret-delivery-token" not in str(stored.encrypted_config)


async def test_viewer_cannot_create_dispatch_alert_channel(client, auth_headers):
    viewer_headers = await _create_viewer_headers(client, auth_headers)

    resp = await client.post(
        "/api/v1/analytics/dispatch-alert-channels",
        json=_channel_payload(),
        headers=viewer_headers,
    )

    assert resp.status_code == 403


async def test_dispatch_alert_channel_rejects_private_url(client, auth_headers):
    resp = await client.post(
        "/api/v1/analytics/dispatch-alert-channels",
        json=_channel_payload("http://127.0.0.1:9000/internal"),
        headers=auth_headers,
    )

    assert resp.status_code == 422
    assert "private" in resp.json()["detail"].lower()


async def test_dispatch_alert_delivery_posts_webhook_and_writes_audit(
    client,
    auth_headers,
    registered_user,
    db_session,
    monkeypatch,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    workflow = await _create_workflow(db_session, tenant_id)
    await _create_dead_letter_execution(db_session, tenant_id, workflow.id)

    channel_resp = await client.post(
        "/api/v1/analytics/dispatch-alert-channels",
        json=_channel_payload(),
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
                    "target": "Ops webhook",
                    "credential_id": channel["id"],
                    "enabled": True,
                }
            ],
            "severities": ["critical"],
            "alert_codes": ["dead_lettered"],
            "cooldown_minutes": 15,
        },
        headers=auth_headers,
    )
    assert policy_resp.status_code == 200, policy_resp.text

    calls = []

    async def fake_deliver_webhook(config, alerts):
        calls.append({"config": config, "alerts": alerts})
        return SimpleNamespace(status="delivered", status_code=202, error_message=None)

    monkeypatch.setattr(
        "app.services.analytics_service._deliver_webhook_notification",
        fake_deliver_webhook,
    )

    resp = await client.post(
        "/api/v1/analytics/dispatch-alert-deliveries",
        headers=auth_headers,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["attempted"] == 1
    assert data["delivered"] == 1
    assert data["failed"] == 0
    assert data["items"][0]["status"] == "delivered"
    assert data["items"][0]["alert_code"] == "dead_lettered"
    assert "secret-delivery-token" not in str(data)
    assert "secret-webhook-header" not in str(data)
    assert "secret-lead" not in str(data)

    assert calls[0]["config"]["headers"]["Authorization"] == "Bearer secret-delivery-token"
    assert calls[0]["alerts"][0].code == "dead_lettered"

    audit_rows = (
        await db_session.execute(select(DispatchAlertDelivery).where(
            DispatchAlertDelivery.tenant_id == tenant_id
        ))
    ).scalars().all()
    assert len(audit_rows) == 1
    assert audit_rows[0].status == "delivered"
    assert audit_rows[0].target_preview == "https://8.8.8.8/dispatch"
    assert "secret-delivery-token" not in str(audit_rows[0].__dict__)

    listed = await client.get(
        "/api/v1/analytics/dispatch-alert-deliveries",
        headers=auth_headers,
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["items"][0]["status"] == "delivered"


async def test_dispatch_alert_delivery_audit_is_tenant_scoped(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    db_session.add(
        DispatchAlertDelivery(
            tenant_id=tenant_id,
            alert_code="dead_lettered",
            channel_type="webhook",
            target_preview="https://8.8.8.8/dispatch",
            status="delivered",
            status_code=202,
        )
    )
    await db_session.commit()

    other = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"dispatch-delivery-other-{uuid.uuid4()}@test.com",
            "password": "securepass123",
            "full_name": "Other Delivery User",
            "tenant_name": "Other Delivery Tenant",
        },
    )
    assert other.status_code == 201, other.text
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}

    resp = await client.get(
        "/api/v1/analytics/dispatch-alert-deliveries",
        headers=other_headers,
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["items"] == []
