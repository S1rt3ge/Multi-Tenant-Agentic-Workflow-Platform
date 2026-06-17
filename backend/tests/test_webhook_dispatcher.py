"""Tests for M11 webhook dispatch pipeline."""

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
import uuid

from sqlalchemy import select

from app.models.execution import Execution, ExecutionLog
from app.services.webhook_dispatcher_service import (
    WebhookRetryPolicy,
    dispatch_pending_webhook_executions,
    is_webhook_trigger_execution,
)


async def _create_workflow(client, headers: dict, definition: dict | None = None) -> dict:
    resp = await client.post(
        "/api/v1/workflows/",
        json={"name": f"Webhook Dispatcher {uuid.uuid4()}", "description": "M11 test"},
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


def _missing_credential_connector_definition() -> dict:
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
                    "credential_id": str(uuid.uuid4()),
                    "input": {
                        "url": "https://example.com/",
                        "method": "GET",
                        "headers": {"Accept": "application/json"},
                    },
                },
            }
        ],
        "edges": [],
    }


async def _create_webhook_pending_execution(client, headers: dict) -> dict:
    workflow = await _create_workflow(
        client,
        headers,
        _missing_credential_connector_definition(),
    )
    trigger = await client.post(
        f"/api/v1/workflows/{workflow['id']}/triggers",
        json={"trigger_type": "webhook", "config": {"auth": "none"}},
        headers=headers,
    )
    assert trigger.status_code == 201, trigger.text

    ingest = await client.post(
        f"/api/v1/webhooks/{trigger.json()['public_id']}",
        json={"lead_id": f"lead-{uuid.uuid4()}"},
        headers={"X-Api-Key": "secret-webhook-header"},
    )
    assert ingest.status_code == 202, ingest.text

    return {
        "workflow": workflow,
        "trigger": trigger.json(),
        "execution_id": ingest.json()["execution_id"],
    }


async def _create_pending_webhook_execution_row(
    client,
    headers: dict,
    db_session,
    *,
    input_data: dict | None = None,
) -> Execution:
    workflow = await _create_workflow(
        client,
        headers,
        _missing_credential_connector_definition(),
    )
    execution = Execution(
        tenant_id=uuid.UUID(workflow["tenant_id"]),
        workflow_id=uuid.UUID(workflow["id"]),
        status="pending",
        input_data=input_data
        or {
            "trigger": {"type": "webhook", "trigger_id": "trigger-1", "event_id": "event-1"},
            "payload": {"lead_id": f"lead-{uuid.uuid4()}"},
        },
    )
    db_session.add(execution)
    await db_session.commit()
    await db_session.refresh(execution)
    return execution


async def _fake_retryable_failure(
    execution_id,
    workflow_id,
    tenant_id,
    input_data,
    db,
) -> None:
    _ = (workflow_id, tenant_id, input_data)
    execution = await db.get(Execution, execution_id)
    execution.status = "failed"
    execution.error_message = "HTTP connector returned status 503."
    db.add(
        ExecutionLog(
            execution_id=execution_id,
            step_number=1,
            agent_name="HTTP Request",
            action="connector_error",
            input_data={"url": "https://example.com/"},
            output_data={"status_code": 503},
            tokens_used=0,
            cost=0.0,
            node_type="connector",
            connector_key="http",
            action_key="request",
            retryable=True,
            sanitized_error="HTTP connector returned status 503.",
        )
    )
    await db.commit()


def test_detects_webhook_trigger_execution():
    webhook_execution = SimpleNamespace(
        input_data={"trigger": {"type": "webhook"}, "payload": {"lead_id": "lead-1"}}
    )
    manual_execution = SimpleNamespace(input_data={"text": "manual run"})
    empty_execution = SimpleNamespace(input_data=None)

    assert is_webhook_trigger_execution(webhook_execution) is True
    assert is_webhook_trigger_execution(manual_execution) is False
    assert is_webhook_trigger_execution(empty_execution) is False


async def test_dispatches_pending_webhook_execution_to_terminal_state(
    client,
    auth_headers,
    db_session,
):
    created = await _create_webhook_pending_execution(client, auth_headers)

    report = await dispatch_pending_webhook_executions(db_session, limit=10)

    assert report.dispatched == 1
    assert created["execution_id"] in report.execution_ids

    execution = await client.get(
        f"/api/v1/executions/{created['execution_id']}",
        headers=auth_headers,
    )
    assert execution.status_code == 200, execution.text
    assert execution.json()["status"] == "failed"

    logs = await client.get(
        f"/api/v1/executions/{created['execution_id']}/logs",
        headers=auth_headers,
    )
    assert logs.status_code == 200, logs.text
    assert logs.json()[0]["node_type"] == "connector"
    assert logs.json()[0]["action"] == "connector_error"


async def test_dispatcher_skips_non_webhook_pending_execution(
    client,
    auth_headers,
    db_session,
):
    workflow = await _create_workflow(
        client,
        auth_headers,
        _missing_credential_connector_definition(),
    )
    execution = Execution(
        tenant_id=uuid.UUID(workflow["tenant_id"]),
        workflow_id=uuid.UUID(workflow["id"]),
        status="pending",
        input_data={"text": "manual pending execution"},
    )
    db_session.add(execution)
    await db_session.commit()
    await db_session.refresh(execution)

    report = await dispatch_pending_webhook_executions(db_session, limit=10)

    await db_session.refresh(execution)
    assert report.dispatched == 0
    assert report.skipped == 1
    assert execution.status == "pending"


async def test_dispatcher_respects_limit_for_webhook_executions(
    client,
    auth_headers,
    db_session,
):
    first = await _create_webhook_pending_execution(client, auth_headers)
    second = await _create_webhook_pending_execution(client, auth_headers)

    report = await dispatch_pending_webhook_executions(db_session, limit=1)

    assert report.dispatched == 1
    assert len(report.execution_ids) == 1
    assert set(report.execution_ids).issubset(
        {first["execution_id"], second["execution_id"]}
    )

    result = await db_session.execute(
        select(Execution).where(
            Execution.id.in_(
                [uuid.UUID(first["execution_id"]), uuid.UUID(second["execution_id"])]
            )
        )
    )
    statuses = sorted(execution.status for execution in result.scalars().all())
    assert statuses == ["failed", "pending"]


async def test_retryable_failure_schedules_new_pending_retry_execution(
    client,
    auth_headers,
    db_session,
    monkeypatch,
):
    now = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)
    execution = await _create_pending_webhook_execution_row(
        client,
        auth_headers,
        db_session,
    )
    monkeypatch.setattr(
        "app.services.webhook_dispatcher_service.run_execution",
        _fake_retryable_failure,
    )

    report = await dispatch_pending_webhook_executions(
        db_session,
        limit=10,
        retry_policy=WebhookRetryPolicy(max_attempts=3, backoff_seconds=45),
        now=now,
    )

    assert report.dispatched == 1
    assert report.retries_scheduled == 1

    result = await db_session.execute(
        select(Execution).where(Execution.workflow_id == execution.workflow_id)
    )
    executions = sorted(result.scalars().all(), key=lambda item: str(item.id))
    retry = next(item for item in executions if item.status == "pending")
    dispatch = retry.input_data["dispatch"]

    assert dispatch["attempt"] == 2
    assert dispatch["root_execution_id"] == str(execution.id)
    assert dispatch["parent_execution_id"] == str(execution.id)
    assert dispatch["previous_execution_id"] == str(execution.id)
    assert dispatch["next_attempt_at"] == (now + timedelta(seconds=45)).isoformat()


async def test_retry_execution_is_deferred_until_next_attempt(
    client,
    auth_headers,
    db_session,
    monkeypatch,
):
    now = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)
    called = False

    async def fail_if_called(*args, **kwargs):
        nonlocal called
        called = True

    execution = await _create_pending_webhook_execution_row(
        client,
        auth_headers,
        db_session,
        input_data={
            "trigger": {"type": "webhook", "trigger_id": "trigger-1", "event_id": "event-1"},
            "payload": {"lead_id": "lead-1"},
            "dispatch": {
                "attempt": 2,
                "next_attempt_at": (now + timedelta(seconds=60)).isoformat(),
            },
        },
    )
    monkeypatch.setattr(
        "app.services.webhook_dispatcher_service.run_execution",
        fail_if_called,
    )

    report = await dispatch_pending_webhook_executions(
        db_session,
        limit=10,
        retry_policy=WebhookRetryPolicy(max_attempts=3, backoff_seconds=45),
        now=now,
    )

    await db_session.refresh(execution)
    assert called is False
    assert report.dispatched == 0
    assert report.deferred == 1
    assert execution.status == "pending"


async def test_exhausted_retryable_failure_is_dead_lettered(
    client,
    auth_headers,
    db_session,
    monkeypatch,
):
    now = datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc)
    execution = await _create_pending_webhook_execution_row(
        client,
        auth_headers,
        db_session,
        input_data={
            "trigger": {"type": "webhook", "trigger_id": "trigger-1", "event_id": "event-1"},
            "payload": {"lead_id": "lead-1"},
            "dispatch": {"attempt": 3, "root_execution_id": "root-1"},
        },
    )
    monkeypatch.setattr(
        "app.services.webhook_dispatcher_service.run_execution",
        _fake_retryable_failure,
    )

    report = await dispatch_pending_webhook_executions(
        db_session,
        limit=10,
        retry_policy=WebhookRetryPolicy(max_attempts=3, backoff_seconds=45),
        now=now,
    )

    await db_session.refresh(execution)
    result = await db_session.execute(
        select(Execution).where(Execution.workflow_id == execution.workflow_id)
    )
    executions = list(result.scalars().all())

    assert report.dispatched == 1
    assert report.dead_lettered == 1
    assert len(executions) == 1
    assert execution.status == "failed"
    assert execution.input_data["dispatch"]["dead_lettered"] is True
    assert execution.input_data["dispatch"]["dead_letter_reason"] == "max_attempts_exhausted"
