"""Tests for M12 scheduled dispatch alert evaluation and cooldown."""

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from sqlalchemy import select

from app.core.config import Settings
from app.models.dispatch_alert import DispatchAlertDelivery
from app.models.execution import Execution
from app.models.workflow import Workflow
from app.services import analytics_service
from app.services.dispatch_alert_evaluator_worker import (
    DispatchAlertEvaluationWorker,
    install_dispatch_alert_evaluator_worker,
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


async def _create_workflow(db_session, tenant_id: uuid.UUID) -> Workflow:
    workflow = Workflow(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="Dispatch Alert Evaluator WF",
        description="dispatch alert evaluator test",
        definition={"nodes": [], "edges": []},
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


def _channel_payload() -> dict:
    return {
        "name": "Ops evaluator webhook",
        "channel_type": "webhook",
        "config": {
            "url": "https://8.8.8.8/dispatch",
            "headers": {
                "Authorization": "Bearer secret-evaluator-token",
                "X-Team": "ops",
            },
        },
    }


async def _create_channel(client, auth_headers: dict) -> dict:
    resp = await client.post(
        "/api/v1/analytics/dispatch-alert-channels",
        json=_channel_payload(),
        headers=auth_headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def _configure_policy(
    client,
    auth_headers: dict,
    channel_id: str,
    cooldown_minutes: int = 30,
) -> dict:
    resp = await client.put(
        "/api/v1/analytics/dispatch-alert-policy",
        json={
            "enabled": True,
            "channels": [
                {
                    "type": "webhook",
                    "target": "Ops evaluator webhook",
                    "credential_id": channel_id,
                    "enabled": True,
                }
            ],
            "severities": ["critical"],
            "alert_codes": ["dead_lettered"],
            "cooldown_minutes": cooldown_minutes,
        },
        headers=auth_headers,
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


async def _prepare_alerting_tenant(client, auth_headers, registered_user, db_session):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    workflow = await _create_workflow(db_session, tenant_id)
    await _create_dead_letter_execution(db_session, tenant_id, workflow.id)
    channel = await _create_channel(client, auth_headers)
    await _configure_policy(client, auth_headers, channel["id"], cooldown_minutes=30)
    return tenant_id, channel


def test_evaluator_settings_default_to_disabled():
    settings = Settings()

    assert settings.DISPATCH_ALERT_EVALUATOR_ENABLED is False
    assert settings.DISPATCH_ALERT_EVALUATOR_INTERVAL_SECONDS == 60.0
    assert settings.DISPATCH_ALERT_EVALUATOR_TENANT_LIMIT == 25
    assert settings.DISPATCH_ALERT_EVALUATOR_WINDOW_HOURS == 24


def test_evaluator_settings_can_be_enabled_and_configured():
    settings = Settings(
        DISPATCH_ALERT_EVALUATOR_ENABLED=True,
        DISPATCH_ALERT_EVALUATOR_INTERVAL_SECONDS=2.5,
        DISPATCH_ALERT_EVALUATOR_TENANT_LIMIT=7,
        DISPATCH_ALERT_EVALUATOR_WINDOW_HOURS=12,
    )

    assert settings.DISPATCH_ALERT_EVALUATOR_ENABLED is True
    assert settings.DISPATCH_ALERT_EVALUATOR_INTERVAL_SECONDS == 2.5
    assert settings.DISPATCH_ALERT_EVALUATOR_TENANT_LIMIT == 7
    assert settings.DISPATCH_ALERT_EVALUATOR_WINDOW_HOURS == 12


def test_lifecycle_installer_leaves_worker_absent_when_disabled():
    app = FastAPI()
    settings = Settings(DISPATCH_ALERT_EVALUATOR_ENABLED=False)

    install_dispatch_alert_evaluator_worker(app, settings)

    assert getattr(app.state, "dispatch_alert_evaluator_worker", None) is None


def test_lifecycle_installer_registers_worker_when_enabled():
    app = FastAPI()
    app.state.db_session_factory = FakeSessionFactory()
    settings = Settings(
        DISPATCH_ALERT_EVALUATOR_ENABLED=True,
        DISPATCH_ALERT_EVALUATOR_INTERVAL_SECONDS=0.5,
        DISPATCH_ALERT_EVALUATOR_TENANT_LIMIT=7,
        DISPATCH_ALERT_EVALUATOR_WINDOW_HOURS=12,
    )

    install_dispatch_alert_evaluator_worker(app, settings)

    worker = app.state.dispatch_alert_evaluator_worker
    assert isinstance(worker, DispatchAlertEvaluationWorker)
    assert worker.interval_seconds == 0.5
    assert worker.tenant_limit == 7
    assert worker.window_hours == 12


async def test_evaluator_worker_loop_starts_and_stops_cleanly():
    calls = []

    async def fake_evaluate(_db, limit: int, window_hours: int):
        calls.append((limit, window_hours))
        return None

    worker = DispatchAlertEvaluationWorker(
        session_factory=FakeSessionFactory(),
        interval_seconds=0.01,
        tenant_limit=3,
        window_hours=6,
        evaluate_func=fake_evaluate,
    )

    worker.start()
    await asyncio.sleep(0.04)
    await worker.stop()

    assert calls
    assert set(calls) == {(3, 6)}
    assert worker.is_running is False


async def test_delivery_cooldown_suppresses_repeated_alert(
    client,
    auth_headers,
    registered_user,
    db_session,
    monkeypatch,
):
    tenant_id, _channel = await _prepare_alerting_tenant(
        client,
        auth_headers,
        registered_user,
        db_session,
    )
    calls = []

    async def fake_deliver_webhook(config, alerts):
        calls.append({"config": config, "alerts": alerts})
        return SimpleNamespace(status="delivered", status_code=202, error_message=None)

    monkeypatch.setattr(
        "app.services.analytics_service._deliver_webhook_notification",
        fake_deliver_webhook,
    )

    first = await analytics_service.deliver_dispatch_alerts(db_session, tenant_id)
    second = await analytics_service.deliver_dispatch_alerts(db_session, tenant_id)

    assert first.attempted == 1
    assert first.delivered == 1
    assert second.attempted == 0
    assert second.delivered == 0
    assert second.skipped == 1
    assert len(calls) == 1

    rows = (
        await db_session.execute(
            select(DispatchAlertDelivery).where(
                DispatchAlertDelivery.tenant_id == tenant_id
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert "secret-evaluator-token" not in str(second)
    assert "secret-webhook-header" not in str(second)
    assert "secret-lead" not in str(second)


async def test_delivery_resumes_after_cooldown_window(
    client,
    auth_headers,
    registered_user,
    db_session,
    monkeypatch,
):
    tenant_id, channel = await _prepare_alerting_tenant(
        client,
        auth_headers,
        registered_user,
        db_session,
    )
    await _configure_policy(client, auth_headers, channel["id"], cooldown_minutes=5)
    db_session.add(
        DispatchAlertDelivery(
            tenant_id=tenant_id,
            channel_id=uuid.UUID(channel["id"]),
            alert_code="dead_lettered",
            channel_type="webhook",
            target_preview="https://8.8.8.8/dispatch",
            status="delivered",
            status_code=202,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=6),
        )
    )
    await db_session.commit()
    calls = []

    async def fake_deliver_webhook(config, alerts):
        calls.append({"config": config, "alerts": alerts})
        return SimpleNamespace(status="delivered", status_code=202, error_message=None)

    monkeypatch.setattr(
        "app.services.analytics_service._deliver_webhook_notification",
        fake_deliver_webhook,
    )

    result = await analytics_service.deliver_dispatch_alerts(db_session, tenant_id)

    assert result.attempted == 1
    assert result.delivered == 1
    assert result.skipped == 0
    assert len(calls) == 1


async def test_evaluator_run_once_evaluates_tenant_policy(
    client,
    auth_headers,
    registered_user,
    db_session,
    monkeypatch,
):
    tenant_id, _channel = await _prepare_alerting_tenant(
        client,
        auth_headers,
        registered_user,
        db_session,
    )
    calls = []

    async def fake_deliver_webhook(config, alerts):
        calls.append({"config": config, "alerts": alerts})
        return SimpleNamespace(status="delivered", status_code=202, error_message=None)

    monkeypatch.setattr(
        "app.services.analytics_service._deliver_webhook_notification",
        fake_deliver_webhook,
    )
    worker = DispatchAlertEvaluationWorker(
        session_factory=ExistingSessionFactory(db_session),
        interval_seconds=0.01,
        tenant_limit=10,
        window_hours=24,
    )

    report = await worker.run_once()

    assert report.tenants_scanned >= 1
    assert report.tenants_evaluated == 1
    assert str(tenant_id) in report.tenant_ids
    assert report.attempted == 1
    assert report.delivered == 1
    assert report.failed == 0
    assert report.skipped == 0
    assert len(calls) == 1
    assert "secret-evaluator-token" not in str(report)
    assert "secret-webhook-header" not in str(report)
    assert "secret-lead" not in str(report)
