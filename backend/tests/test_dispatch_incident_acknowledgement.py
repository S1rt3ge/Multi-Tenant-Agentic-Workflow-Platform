"""Tests for M12 dispatch incident acknowledgement and ownership."""

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
        name="Dispatch Acknowledgement WF",
        description="dispatch acknowledgement test",
        definition={"nodes": [{"id": "secret-node", "data": {"token": "secret-workflow-token"}}]},
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


async def _prepare_incident(registered_user, db_session) -> uuid.UUID:
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    workflow = await _create_workflow(db_session, tenant_id)
    await _create_dead_letter_execution(db_session, tenant_id, workflow.id)
    return tenant_id


async def _viewer_headers(client, auth_headers: dict) -> dict:
    invite = await client.post(
        "/api/v1/tenants/invite",
        json={"email": f"ack-viewer-{uuid.uuid4()}@test.com", "role": "viewer"},
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


async def test_acknowledgement_read_requires_auth(client):
    resp = await client.get("/api/v1/analytics/dispatch-incident-acknowledgement")

    assert resp.status_code == 401


async def test_owner_can_acknowledge_active_dispatch_incident(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    tenant_id = await _prepare_incident(registered_user, db_session)

    resp = await client.post(
        "/api/v1/analytics/dispatch-incident-acknowledgement",
        json={"note": "Taking ownership. Authorization: Bearer secret-ack-token"},
        headers=auth_headers,
    )

    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["tenant_id"] == str(tenant_id)
    assert data["status"] == "acknowledged"
    assert data["alert_codes"] == ["dead_lettered"]
    assert data["acknowledged_by_email"] == registered_user["email"]
    assert data["note"].startswith("Taking ownership.")
    assert "secret-ack-token" not in str(data)
    assert "secret-webhook-header" not in str(data)
    assert "secret-workflow-token" not in str(data)
    assert "secret-lead" not in str(data)

    state = await client.get(
        "/api/v1/analytics/dispatch-incident-acknowledgement",
        headers=auth_headers,
    )
    assert state.status_code == 200, state.text
    assert state.json()["acknowledgement"]["id"] == data["id"]

    runbook = await client.get("/api/v1/analytics/dispatch-runbook", headers=auth_headers)
    assert runbook.status_code == 200, runbook.text
    assert runbook.json()["acknowledgement"]["acknowledged_by_email"] == registered_user["email"]


async def test_viewer_cannot_acknowledge_dispatch_incident(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    await _prepare_incident(registered_user, db_session)
    viewer_headers = await _viewer_headers(client, auth_headers)

    resp = await client.post(
        "/api/v1/analytics/dispatch-incident-acknowledgement",
        json={"note": "I should not own this"},
        headers=viewer_headers,
    )

    assert resp.status_code == 403


async def test_quiet_runbook_state_cannot_be_acknowledged(client, auth_headers):
    resp = await client.post(
        "/api/v1/analytics/dispatch-incident-acknowledgement",
        json={"note": "Nothing to own"},
        headers=auth_headers,
    )

    assert resp.status_code == 409


async def test_reacknowledgement_updates_current_owner_without_duplicate_rows(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    tenant_id = await _prepare_incident(registered_user, db_session)
    first = await client.post(
        "/api/v1/analytics/dispatch-incident-acknowledgement",
        json={"note": "First owner"},
        headers=auth_headers,
    )
    assert first.status_code == 201, first.text

    invite = await client.post(
        "/api/v1/tenants/invite",
        json={"email": f"ack-editor-{uuid.uuid4()}@test.com", "role": "editor"},
        headers=auth_headers,
    )
    assert invite.status_code == 201, invite.text
    editor = invite.json()
    editor_user = await db_session.get(User, uuid.UUID(editor["id"]))
    editor_user.must_change_password = False
    await db_session.commit()
    editor_headers = {
        "Authorization": f"Bearer {create_access_token(
            user_id=uuid.UUID(editor['id']),
            tenant_id=uuid.UUID(editor['tenant_id']),
            role='editor',
        )}"
    }

    second = await client.post(
        "/api/v1/analytics/dispatch-incident-acknowledgement",
        json={"note": "Second owner token=secret-second-token"},
        headers=editor_headers,
    )

    assert second.status_code == 201, second.text
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["acknowledged_by_email"] == editor["email"]
    assert "secret-second-token" not in str(second.json())

    rows = (
        await db_session.execute(
            select(DispatchIncidentAcknowledgement).where(
                DispatchIncidentAcknowledgement.tenant_id == tenant_id
            )
        )
    ).scalars().all()
    assert len(rows) == 1


async def test_acknowledgement_is_tenant_scoped(
    client,
    auth_headers,
    registered_user,
    db_session,
):
    await _prepare_incident(registered_user, db_session)
    ack = await client.post(
        "/api/v1/analytics/dispatch-incident-acknowledgement",
        json={"note": "Owner"},
        headers=auth_headers,
    )
    assert ack.status_code == 201, ack.text

    other = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"ack-other-{uuid.uuid4()}@test.com",
            "password": "securepass123",
            "full_name": "Other Ack User",
            "tenant_name": "Other Ack Tenant",
        },
    )
    assert other.status_code == 201, other.text
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}

    state = await client.get(
        "/api/v1/analytics/dispatch-incident-acknowledgement",
        headers=other_headers,
    )

    assert state.status_code == 200, state.text
    assert state.json()["acknowledgement"] is None
