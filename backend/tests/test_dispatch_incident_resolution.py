"""Tests for M12 dispatch incident resolution history and review notes."""

import uuid

from sqlalchemy import select

from app.core.security import create_access_token
from app.models.dispatch_alert import DispatchIncidentAcknowledgement
from app.models.execution import Execution
from app.models.user import User
from app.models.workflow import Workflow


async def _create_workflow(db_session, tenant_id: uuid.UUID) -> Workflow:
    workflow = Workflow(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="Dispatch Resolution WF",
        description="dispatch resolution test",
        definition={"nodes": [{"id": "secret-node", "data": {"token": "secret-workflow-token"}}]},
    )
    db_session.add(workflow)
    await db_session.commit()
    await db_session.refresh(workflow)
    return workflow


async def _create_dead_letter_execution(db_session, tenant_id: uuid.UUID, workflow_id: uuid.UUID):
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


async def _prepare_incident(registered_user, db_session) -> uuid.UUID:
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    workflow = await _create_workflow(db_session, tenant_id)
    await _create_dead_letter_execution(db_session, tenant_id, workflow.id)
    return tenant_id


async def _acknowledge(client, headers: dict):
    resp = await client.post(
        "/api/v1/analytics/dispatch-incident-acknowledgement",
        json={"note": "Taking ownership"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _viewer_headers(client, auth_headers: dict, db_session) -> dict:
    invite = await client.post(
        "/api/v1/tenants/invite",
        json={"email": f"resolution-viewer-{uuid.uuid4()}@test.com", "role": "viewer"},
        headers=auth_headers,
    )
    assert invite.status_code == 201, invite.text
    viewer = invite.json()
    viewer_user = await db_session.get(User, uuid.UUID(viewer["id"]))
    viewer_user.must_change_password = False
    await db_session.commit()
    token = create_access_token(
        user_id=uuid.UUID(viewer["id"]),
        tenant_id=uuid.UUID(viewer["tenant_id"]),
        role="viewer",
    )
    return {"Authorization": f"Bearer {token}"}


async def test_owner_can_resolve_acknowledged_dispatch_incident(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    tenant_id = await _prepare_incident(registered_user, db_session)
    ack = await _acknowledge(client, auth_headers)

    resp = await client.post(
        "/api/v1/analytics/dispatch-incident-acknowledgement/resolve",
        json={"resolution_note": "Fixed downstream token=secret-resolution-token"},
        headers=auth_headers,
    )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["id"] == ack["id"]
    assert data["tenant_id"] == str(tenant_id)
    assert data["status"] == "resolved"
    assert data["resolved_by_email"] == registered_user["email"]
    assert data["resolution_note"].endswith("token=****")
    assert "secret-resolution-token" not in str(data)
    assert "secret-webhook-header" not in str(data)
    assert "secret-workflow-token" not in str(data)
    assert "secret-lead" not in str(data)

    state = await client.get(
        "/api/v1/analytics/dispatch-incident-acknowledgement",
        headers=auth_headers,
    )
    assert state.status_code == 200, state.text
    assert state.json()["acknowledgement"] is None

    runbook = await client.get("/api/v1/analytics/dispatch-runbook", headers=auth_headers)
    assert runbook.status_code == 200, runbook.text
    assert runbook.json()["acknowledgement"] is None


async def test_viewer_cannot_resolve_dispatch_incident(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    await _prepare_incident(registered_user, db_session)
    await _acknowledge(client, auth_headers)
    viewer_headers = await _viewer_headers(client, auth_headers, db_session)

    resp = await client.post(
        "/api/v1/analytics/dispatch-incident-acknowledgement/resolve",
        json={"resolution_note": "I should not resolve this"},
        headers=viewer_headers,
    )

    assert resp.status_code == 403


async def test_resolve_without_open_acknowledgement_returns_conflict(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    await _prepare_incident(registered_user, db_session)

    resp = await client.post(
        "/api/v1/analytics/dispatch-incident-acknowledgement/resolve",
        json={"resolution_note": "Nothing acknowledged"},
        headers=auth_headers,
    )

    assert resp.status_code == 409


async def test_incident_history_is_tenant_scoped(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    tenant_id = await _prepare_incident(registered_user, db_session)
    await _acknowledge(client, auth_headers)
    resolved = await client.post(
        "/api/v1/analytics/dispatch-incident-acknowledgement/resolve",
        json={"resolution_note": "Resolved"},
        headers=auth_headers,
    )
    assert resolved.status_code == 200, resolved.text

    history = await client.get(
        "/api/v1/analytics/dispatch-incident-history",
        headers=auth_headers,
    )
    assert history.status_code == 200, history.text
    data = history.json()
    assert len(data["items"]) == 1
    assert data["items"][0]["tenant_id"] == str(tenant_id)
    assert data["items"][0]["status"] == "resolved"

    other = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"resolution-other-{uuid.uuid4()}@test.com",
            "password": "securepass123",
            "full_name": "Other Resolution User",
            "tenant_name": "Other Resolution Tenant",
        },
    )
    assert other.status_code == 201, other.text
    other_history = await client.get(
        "/api/v1/analytics/dispatch-incident-history",
        headers={"Authorization": f"Bearer {other.json()['access_token']}"},
    )
    assert other_history.status_code == 200, other_history.text
    assert other_history.json()["items"] == []

    rows = (
        await db_session.execute(
            select(DispatchIncidentAcknowledgement).where(
                DispatchIncidentAcknowledgement.tenant_id == tenant_id
            )
        )
    ).scalars().all()
    assert len(rows) == 1
