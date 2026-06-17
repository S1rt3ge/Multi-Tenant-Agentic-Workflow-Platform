"""Tests for M12 operator-grade dispatch controls."""

import uuid

from sqlalchemy import select

from app.models.execution import Execution


async def _create_workflow(client, headers: dict, definition: dict | None = None) -> dict:
    resp = await client.post(
        "/api/v1/workflows/",
        json={"name": f"Dispatch Controls {uuid.uuid4()}", "description": "M12 test"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    workflow = resp.json()

    if definition is not None:
        update = await client.put(
            f"/api/v1/workflows/{workflow['id']}",
            json={"definition": definition},
            headers=headers,
        )
        assert update.status_code == 200, update.text
        workflow = update.json()

    return workflow


def _single_connector_definition() -> dict:
    return {
        "nodes": [
            {
                "id": "http-1",
                "type": "connector",
                "position": {"x": 0, "y": 0},
                "data": {
                    "label": "HTTP Request",
                    "connector_key": "http",
                    "action_key": "request",
                    "input": {
                        "url": "https://example.com/",
                        "method": "GET",
                    },
                },
            }
        ],
        "edges": [],
    }


async def _create_dead_letter_execution(client, headers: dict, db_session) -> Execution:
    workflow = await _create_workflow(client, headers, _single_connector_definition())
    execution_id = uuid.uuid4()
    execution = Execution(
        id=execution_id,
        tenant_id=uuid.UUID(workflow["tenant_id"]),
        workflow_id=uuid.UUID(workflow["id"]),
        status="failed",
        error_message="HTTP connector returned status 503.",
        input_data={
            "trigger": {"type": "webhook", "trigger_id": "trigger-1", "event_id": "event-1"},
            "payload": {"lead_id": "lead-123"},
            "headers": {"x-webhook-secret": "secret-webhook-header"},
            "dispatch": {
                "attempt": 3,
                "root_execution_id": str(execution_id),
                "parent_execution_id": "parent-execution",
                "previous_execution_id": "previous-execution",
                "dead_lettered": True,
                "dead_letter_reason": "max_attempts_exhausted",
                "next_attempt_at": "2026-05-17T10:00:00+00:00",
            },
        },
    )
    db_session.add(execution)
    await db_session.commit()
    await db_session.refresh(execution)
    return execution


async def test_editor_can_retry_dead_lettered_webhook_execution(
    client,
    auth_headers,
    db_session,
):
    source = await _create_dead_letter_execution(client, auth_headers, db_session)

    resp = await client.post(
        f"/api/v1/executions/{source.id}/retry",
        headers=auth_headers,
    )

    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["status"] == "pending"
    assert data["source_execution_id"] == str(source.id)
    assert data["execution_id"] != str(source.id)

    await db_session.refresh(source)
    retry = await db_session.get(Execution, uuid.UUID(data["execution_id"]))

    assert source.status == "failed"
    assert source.input_data["dispatch"]["dead_lettered"] is True
    assert retry.status == "pending"
    assert retry.workflow_id == source.workflow_id
    assert retry.tenant_id == source.tenant_id
    assert retry.input_data["trigger"]["type"] == "webhook"
    assert retry.input_data["payload"] == {"lead_id": "lead-123"}

    dispatch = retry.input_data["dispatch"]
    assert dispatch["attempt"] == 4
    assert dispatch["root_execution_id"] == str(source.id)
    assert dispatch["parent_execution_id"] == str(source.id)
    assert dispatch["previous_execution_id"] == str(source.id)
    assert dispatch["manual_retry"] is True
    assert "requested_by_user_id" in dispatch
    assert dispatch["dead_lettered"] is False
    assert "dead_letter_reason" not in dispatch
    assert "next_attempt_at" not in dispatch


async def test_retry_non_dead_letter_execution_returns_conflict(
    client,
    auth_headers,
    db_session,
):
    source = await _create_dead_letter_execution(client, auth_headers, db_session)
    input_data = {
        **source.input_data,
        "dispatch": {
            **source.input_data["dispatch"],
            "dead_lettered": False,
        },
    }
    source.input_data = input_data
    db_session.add(source)
    await db_session.commit()

    resp = await client.post(
        f"/api/v1/executions/{source.id}/retry",
        headers=auth_headers,
    )

    assert resp.status_code == 409
    assert "dead-letter" in resp.json()["detail"].lower()

    result = await db_session.execute(
        select(Execution).where(Execution.workflow_id == source.workflow_id)
    )
    assert len(list(result.scalars().all())) == 1


async def test_viewer_cannot_retry_dead_lettered_execution(
    client,
    auth_headers,
    db_session,
):
    source = await _create_dead_letter_execution(client, auth_headers, db_session)

    invite = await client.post(
        "/api/v1/tenants/invite",
        json={"email": "viewer-dispatch-controls@test.com", "role": "viewer"},
        headers=auth_headers,
    )
    assert invite.status_code == 201

    login = await client.post(
        "/api/v1/auth/login",
        json={
            "email": "viewer-dispatch-controls@test.com",
            "password": invite.json()["temporary_password"],
        },
    )
    viewer_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    set_pass = await client.post(
        "/api/v1/auth/set-password",
        json={"password": "viewerpass123"},
        headers=viewer_headers,
    )
    viewer_headers = {"Authorization": f"Bearer {set_pass.json()['access_token']}"}

    resp = await client.post(
        f"/api/v1/executions/{source.id}/retry",
        headers=viewer_headers,
    )

    assert resp.status_code == 403


async def test_other_tenant_cannot_retry_dead_lettered_execution(
    client,
    auth_headers,
    db_session,
):
    source = await _create_dead_letter_execution(client, auth_headers, db_session)

    other = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "other-dispatch-controls@test.com",
            "password": "password123",
            "full_name": "Other User",
            "tenant_name": "Other Dispatch Tenant",
        },
    )
    assert other.status_code == 201
    other_headers = {"Authorization": f"Bearer {other.json()['access_token']}"}

    resp = await client.post(
        f"/api/v1/executions/{source.id}/retry",
        headers=other_headers,
    )

    assert resp.status_code == 404
