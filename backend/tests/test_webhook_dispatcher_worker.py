"""Tests for M11 webhook dispatcher worker loop."""

import asyncio
import uuid

from fastapi import FastAPI

from app.core.config import Settings
from app.services.webhook_dispatcher_worker import (
    WebhookDispatcherWorker,
    install_webhook_dispatcher_worker,
)


class ExistingSessionFactory:
    def __init__(self, session):
        self.session = session

    def __call__(self):
        return self

    async def __aenter__(self):
        return self.session

    async def __aexit__(self, exc_type, exc, tb):
        return False


class FakeSessionFactory:
    def __call__(self):
        return self

    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return False


async def _create_workflow(client, headers: dict, definition: dict | None = None) -> dict:
    resp = await client.post(
        "/api/v1/workflows/",
        json={"name": f"Worker Dispatcher {uuid.uuid4()}", "description": "M11 worker"},
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

    return {"workflow": workflow, "execution_id": ingest.json()["execution_id"]}


def test_worker_settings_default_to_disabled():
    settings = Settings()

    assert settings.WEBHOOK_DISPATCHER_ENABLED is False
    assert settings.WEBHOOK_DISPATCHER_INTERVAL_SECONDS == 5.0
    assert settings.WEBHOOK_DISPATCHER_BATCH_LIMIT == 10


def test_worker_settings_can_be_enabled_and_configured():
    settings = Settings(
        WEBHOOK_DISPATCHER_ENABLED=True,
        WEBHOOK_DISPATCHER_INTERVAL_SECONDS=0.25,
        WEBHOOK_DISPATCHER_BATCH_LIMIT=3,
    )

    assert settings.WEBHOOK_DISPATCHER_ENABLED is True
    assert settings.WEBHOOK_DISPATCHER_INTERVAL_SECONDS == 0.25
    assert settings.WEBHOOK_DISPATCHER_BATCH_LIMIT == 3


async def test_worker_run_once_dispatches_pending_webhook_execution(
    client,
    auth_headers,
    db_session,
):
    created = await _create_webhook_pending_execution(client, auth_headers)
    worker = WebhookDispatcherWorker(
        session_factory=ExistingSessionFactory(db_session),
        interval_seconds=0.01,
        batch_limit=10,
    )

    report = await worker.run_once()

    assert report.dispatched == 1
    assert created["execution_id"] in report.execution_ids

    execution = await client.get(
        f"/api/v1/executions/{created['execution_id']}",
        headers=auth_headers,
    )
    assert execution.status_code == 200, execution.text
    assert execution.json()["status"] == "failed"


async def test_worker_loop_starts_and_stops_cleanly():
    calls = []

    async def fake_dispatch(_db, limit: int):
        calls.append(limit)

    worker = WebhookDispatcherWorker(
        session_factory=FakeSessionFactory(),
        interval_seconds=0.01,
        batch_limit=3,
        dispatch_func=fake_dispatch,
    )

    worker.start()
    await asyncio.sleep(0.04)
    await worker.stop()

    assert calls
    assert set(calls) == {3}
    assert worker.is_running is False


def test_lifecycle_installer_leaves_worker_absent_when_disabled():
    app = FastAPI()
    settings = Settings(WEBHOOK_DISPATCHER_ENABLED=False)

    install_webhook_dispatcher_worker(app, settings)

    assert getattr(app.state, "webhook_dispatcher_worker", None) is None


def test_lifecycle_installer_registers_worker_when_enabled():
    app = FastAPI()
    app.state.db_session_factory = FakeSessionFactory()
    settings = Settings(
        WEBHOOK_DISPATCHER_ENABLED=True,
        WEBHOOK_DISPATCHER_INTERVAL_SECONDS=0.5,
        WEBHOOK_DISPATCHER_BATCH_LIMIT=7,
    )

    install_webhook_dispatcher_worker(app, settings)

    worker = app.state.webhook_dispatcher_worker
    assert isinstance(worker, WebhookDispatcherWorker)
    assert worker.interval_seconds == 0.5
    assert worker.batch_limit == 7
