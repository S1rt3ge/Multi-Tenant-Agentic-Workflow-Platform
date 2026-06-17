"""Tests for M12 workflow-level webhook dispatch controls."""

import uuid

from app.models.execution import Execution
from app.services.webhook_dispatcher_service import dispatch_pending_webhook_executions


async def _create_workflow(client, headers: dict, name: str = "Dispatch Control WF") -> dict:
    resp = await client.post(
        "/api/v1/workflows/",
        json={"name": f"{name} {uuid.uuid4()}", "description": "M12 dispatch control test"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _viewer_headers(client, owner_headers: dict) -> dict:
    invite = await client.post(
        "/api/v1/tenants/invite",
        json={"email": f"viewer-dispatch-{uuid.uuid4()}@test.com", "role": "viewer"},
        headers=owner_headers,
    )
    assert invite.status_code == 201, invite.text

    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": invite.json()["email"],
            "password": invite.json()["temporary_password"],
        },
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    set_password = await client.post(
        "/api/v1/auth/set-password",
        json={"password": "viewerpass123"},
        headers=headers,
    )
    assert set_password.status_code == 200, set_password.text
    return {"Authorization": f"Bearer {set_password.json()['access_token']}"}


async def test_owner_can_pause_and_resume_workflow_dispatch(client, auth_headers):
    workflow = await _create_workflow(client, auth_headers)

    pause_resp = await client.post(
        f"/api/v1/workflows/{workflow['id']}/dispatch/pause",
        headers=auth_headers,
    )
    assert pause_resp.status_code == 200, pause_resp.text
    paused = pause_resp.json()
    assert paused["dispatch_paused"] is True
    assert paused["dispatch_paused_at"] is not None
    assert paused["dispatch_paused_by"] is not None

    get_resp = await client.get(
        f"/api/v1/workflows/{workflow['id']}",
        headers=auth_headers,
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["dispatch_paused"] is True

    resume_resp = await client.post(
        f"/api/v1/workflows/{workflow['id']}/dispatch/resume",
        headers=auth_headers,
    )
    assert resume_resp.status_code == 200, resume_resp.text
    resumed = resume_resp.json()
    assert resumed["dispatch_paused"] is False
    assert resumed["dispatch_paused_at"] is None
    assert resumed["dispatch_paused_by"] is None


async def test_viewer_cannot_pause_or_resume_workflow_dispatch(client, auth_headers):
    workflow = await _create_workflow(client, auth_headers)
    viewer_headers = await _viewer_headers(client, auth_headers)

    pause_resp = await client.post(
        f"/api/v1/workflows/{workflow['id']}/dispatch/pause",
        headers=viewer_headers,
    )
    assert pause_resp.status_code == 403

    resume_resp = await client.post(
        f"/api/v1/workflows/{workflow['id']}/dispatch/resume",
        headers=viewer_headers,
    )
    assert resume_resp.status_code == 403


async def test_other_tenant_cannot_pause_workflow_dispatch(client, auth_headers):
    workflow = await _create_workflow(client, auth_headers)
    other = await client.post(
        "/api/v1/auth/register",
        json={
            "email": f"other-dispatch-{uuid.uuid4()}@test.com",
            "password": "password123",
            "full_name": "Other User",
            "tenant_name": "Other Dispatch Tenant",
        },
    )
    assert other.status_code == 201
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}

    pause_resp = await client.post(
        f"/api/v1/workflows/{workflow['id']}/dispatch/pause",
        headers=other_headers,
    )
    assert pause_resp.status_code == 404


async def test_dispatcher_skips_paused_workflow_webhook_execution(
    client,
    auth_headers,
    db_session,
    monkeypatch,
):
    workflow = await _create_workflow(client, auth_headers)
    pause_resp = await client.post(
        f"/api/v1/workflows/{workflow['id']}/dispatch/pause",
        headers=auth_headers,
    )
    assert pause_resp.status_code == 200, pause_resp.text

    execution = Execution(
        tenant_id=uuid.UUID(workflow["tenant_id"]),
        workflow_id=uuid.UUID(workflow["id"]),
        status="pending",
        input_data={
            "trigger": {"type": "webhook", "trigger_id": "trigger-1", "event_id": "event-1"},
            "payload": {"lead_id": "lead-1"},
        },
    )
    db_session.add(execution)
    await db_session.commit()
    await db_session.refresh(execution)

    called = False

    async def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True

    monkeypatch.setattr(
        "app.services.webhook_dispatcher_service.run_execution",
        fail_if_called,
    )

    report = await dispatch_pending_webhook_executions(db_session, limit=10)

    await db_session.refresh(execution)
    assert called is False
    assert report.dispatched == 0
    assert report.paused == 1
    assert execution.status == "pending"
