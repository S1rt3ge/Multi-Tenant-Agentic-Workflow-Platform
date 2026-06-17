"""Tests for config-gated dispatch automation scheduler."""

import asyncio
import uuid
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from fastapi import FastAPI
from sqlalchemy import func, select

from app.core.config import Settings
from app.models.dispatch_alert import DispatchAutomationPlan, DispatchAutomationWorkerRun
from app.models.tenant import Tenant
from app.models.workflow import Workflow
from app.services.dispatch_automation_worker_scheduler import (
    DispatchAutomationWorkerScheduler,
    acquire_dispatch_automation_scheduler_lock,
    evaluate_dispatch_automation_workers_for_tenants,
    inspect_dispatch_automation_scheduler_fleet,
    install_dispatch_automation_worker_scheduler,
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


class FakeLeaderLock:
    def __init__(self, acquired: bool):
        self.acquired = acquired
        self.released = False

    async def release(self) -> None:
        self.released = True


class FakeDialectSession:
    def __init__(self, dialect_name: str, scalar_values: list[bool] | None = None):
        self.dialect_name = dialect_name
        self.scalar_values = scalar_values or []
        self.calls = []

    def get_bind(self):
        return SimpleNamespace(dialect=SimpleNamespace(name=self.dialect_name))

    async def execute(self, statement, params=None):
        self.calls.append((str(statement), params or {}))
        value = self.scalar_values.pop(0) if self.scalar_values else True
        return SimpleNamespace(scalar=lambda: value)


async def _enable_worker_config(
    db_session,
    tenant_id: uuid.UUID,
    *,
    interval_minutes: int = 15,
    max_plans_per_run: int = 10,
) -> None:
    tenant = await db_session.get(Tenant, tenant_id)
    tenant.dispatch_automation_worker_config = {
        "enabled": True,
        "interval_minutes": interval_minutes,
        "max_plans_per_run": max_plans_per_run,
    }
    db_session.add(tenant)
    await db_session.commit()


async def _create_approved_resume_plan(
    db_session,
    tenant_id: uuid.UUID,
) -> tuple[Workflow, DispatchAutomationPlan]:
    workflow = Workflow(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="Scheduled Automation WF",
        description="scheduled automation worker test",
        definition={"nodes": [{"id": "node-1", "data": {"token": "secret-workflow-token"}}]},
        dispatch_paused=True,
    )
    plan = DispatchAutomationPlan(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        recommendation_code="auto_resume_guard",
        automation_type="resume_guard",
        status="approved",
        priority="warning",
        title="Resume dispatch safely",
        rationale="Paused dispatch should be resumed after health checks pass.",
        suggested_action="Resume paused workflow dispatch.",
        confidence=0.82,
        evidence=["1 paused workflow"],
        blocked_by=[],
        requested_by_email="owner@test.com",
        approved_by_email="owner@test.com",
        approved_at=datetime.now(timezone.utc),
    )
    db_session.add_all([workflow, plan])
    await db_session.commit()
    await db_session.refresh(workflow)
    await db_session.refresh(plan)
    return workflow, plan


async def _create_tenant(
    db_session,
    *,
    slug: str,
    created_at: datetime | None = None,
    enabled: bool = False,
    interval_minutes: int = 15,
    max_plans_per_run: int = 10,
) -> Tenant:
    tenant = Tenant(
        id=uuid.uuid4(),
        name=f"Scheduler {slug}",
        slug=slug,
        dispatch_automation_worker_config={
            "enabled": enabled,
            "interval_minutes": interval_minutes,
            "max_plans_per_run": max_plans_per_run,
        },
        created_at=created_at,
    )
    db_session.add(tenant)
    await db_session.commit()
    await db_session.refresh(tenant)
    return tenant


def test_automation_scheduler_settings_default_to_disabled():
    settings = Settings()

    assert settings.DISPATCH_AUTOMATION_WORKER_ENABLED is False
    assert settings.DISPATCH_AUTOMATION_WORKER_INTERVAL_SECONDS == 60.0
    assert settings.DISPATCH_AUTOMATION_WORKER_TENANT_LIMIT == 25


def test_automation_scheduler_settings_can_be_enabled_and_configured():
    settings = Settings(
        DISPATCH_AUTOMATION_WORKER_ENABLED=True,
        DISPATCH_AUTOMATION_WORKER_INTERVAL_SECONDS=2.5,
        DISPATCH_AUTOMATION_WORKER_TENANT_LIMIT=7,
    )

    assert settings.DISPATCH_AUTOMATION_WORKER_ENABLED is True
    assert settings.DISPATCH_AUTOMATION_WORKER_INTERVAL_SECONDS == 2.5
    assert settings.DISPATCH_AUTOMATION_WORKER_TENANT_LIMIT == 7


def test_lifecycle_installer_leaves_automation_scheduler_absent_when_disabled():
    app = FastAPI()
    settings = Settings(DISPATCH_AUTOMATION_WORKER_ENABLED=False)

    install_dispatch_automation_worker_scheduler(app, settings)

    assert getattr(app.state, "dispatch_automation_worker_scheduler", None) is None


def test_lifecycle_installer_registers_automation_scheduler_when_enabled():
    app = FastAPI()
    app.state.db_session_factory = FakeSessionFactory()
    settings = Settings(
        DISPATCH_AUTOMATION_WORKER_ENABLED=True,
        DISPATCH_AUTOMATION_WORKER_INTERVAL_SECONDS=0.5,
        DISPATCH_AUTOMATION_WORKER_TENANT_LIMIT=7,
    )

    install_dispatch_automation_worker_scheduler(app, settings)

    worker = app.state.dispatch_automation_worker_scheduler
    assert isinstance(worker, DispatchAutomationWorkerScheduler)
    assert worker.interval_seconds == 0.5
    assert worker.tenant_limit == 7


async def test_automation_scheduler_loop_starts_and_stops_cleanly():
    calls = []

    async def fake_evaluate(_db, limit: int):
        calls.append(limit)
        return None

    worker = DispatchAutomationWorkerScheduler(
        session_factory=FakeSessionFactory(),
        interval_seconds=0.01,
        tenant_limit=3,
        evaluate_func=fake_evaluate,
    )

    worker.start()
    await asyncio.sleep(0.04)
    await worker.stop()

    assert calls
    assert set(calls) == {3}
    assert worker.is_running is False


async def test_postgres_leader_lock_uses_advisory_lock_and_unlock():
    db = FakeDialectSession("postgresql", [True, True])

    lock = await acquire_dispatch_automation_scheduler_lock(db)

    assert lock.acquired is True
    assert "pg_try_advisory_lock" in db.calls[0][0]
    await lock.release()
    assert "pg_advisory_unlock" in db.calls[1][0]


async def test_non_postgres_leader_lock_falls_back_to_acquired_without_sql():
    db = FakeDialectSession("sqlite")

    lock = await acquire_dispatch_automation_scheduler_lock(db)

    assert lock.acquired is True
    await lock.release()
    assert db.calls == []


async def test_scheduler_skips_tenants_with_disabled_config(
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    workflow, plan = await _create_approved_resume_plan(db_session, tenant_id)

    report = await evaluate_dispatch_automation_workers_for_tenants(db_session, limit=10)

    assert report.tenants_scanned == 1
    assert report.tenants_enabled == 0
    assert report.tenants_due == 0
    assert report.claimed == 0
    await db_session.refresh(workflow)
    await db_session.refresh(plan)
    assert workflow.dispatch_paused is True
    assert plan.status == "approved"

    audit_rows = (
        await db_session.execute(select(DispatchAutomationWorkerRun))
    ).scalars().all()
    assert audit_rows == []


async def test_scheduler_skips_without_mutation_when_leader_lock_unavailable(
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    await _enable_worker_config(db_session, tenant_id, max_plans_per_run=1)
    workflow, plan = await _create_approved_resume_plan(db_session, tenant_id)
    lock = FakeLeaderLock(acquired=False)

    async def acquire_lock(_db):
        return lock

    report = await evaluate_dispatch_automation_workers_for_tenants(
        db_session,
        limit=10,
        acquire_lock_func=acquire_lock,
    )

    assert report.lock_acquired is False
    assert report.lock_skipped is True
    assert report.tenants_scanned == 0
    assert report.claimed == 0
    assert lock.released is False
    await db_session.refresh(workflow)
    await db_session.refresh(plan)
    assert workflow.dispatch_paused is True
    assert plan.status == "approved"

    audit_rows = (
        await db_session.execute(select(DispatchAutomationWorkerRun))
    ).scalars().all()
    assert audit_rows == []


async def test_scheduler_runs_enabled_due_tenant_and_writes_scheduled_audit(
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    await _enable_worker_config(db_session, tenant_id, max_plans_per_run=1)
    workflow, plan = await _create_approved_resume_plan(db_session, tenant_id)
    lock = FakeLeaderLock(acquired=True)

    async def acquire_lock(_db):
        return lock

    report = await evaluate_dispatch_automation_workers_for_tenants(
        db_session,
        limit=10,
        acquire_lock_func=acquire_lock,
    )

    assert report.lock_acquired is True
    assert report.lock_skipped is False
    assert report.tenants_scanned == 1
    assert report.tenants_enabled == 1
    assert report.tenants_due == 1
    assert report.claimed == 1
    assert report.executed == 1
    assert report.blocked == 0
    assert report.failed == 0
    assert str(tenant_id) in report.tenant_ids
    assert "secret-workflow-token" not in str(report)

    await db_session.refresh(workflow)
    await db_session.refresh(plan)
    assert workflow.dispatch_paused is False
    assert plan.status == "executed"

    rows = (
        await db_session.execute(
            select(DispatchAutomationWorkerRun).where(
                DispatchAutomationWorkerRun.tenant_id == tenant_id,
                DispatchAutomationWorkerRun.trigger_type == "scheduled",
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "completed"
    assert rows[0].limit == 1
    assert rows[0].claimed == 1
    assert rows[0].executed == 1
    assert rows[0].triggered_by is None
    assert lock.released is True


async def test_scheduler_skips_enabled_tenant_inside_interval(
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    await _enable_worker_config(db_session, tenant_id, interval_minutes=30)
    workflow, plan = await _create_approved_resume_plan(db_session, tenant_id)
    db_session.add(
        DispatchAutomationWorkerRun(
            tenant_id=tenant_id,
            trigger_type="scheduled",
            status="completed",
            limit=10,
            claimed=0,
            executed=0,
            blocked=0,
            failed=0,
            created_at=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
    )
    await db_session.commit()

    report = await evaluate_dispatch_automation_workers_for_tenants(db_session, limit=10)

    assert report.tenants_scanned == 1
    assert report.tenants_enabled == 1
    assert report.tenants_due == 0
    assert report.tenants_skipped_interval == 1
    assert report.claimed == 0
    await db_session.refresh(workflow)
    await db_session.refresh(plan)
    assert workflow.dispatch_paused is True
    assert plan.status == "approved"

    rows = (
        await db_session.execute(
            select(DispatchAutomationWorkerRun).where(
                DispatchAutomationWorkerRun.tenant_id == tenant_id,
                DispatchAutomationWorkerRun.trigger_type == "scheduled",
            )
        )
    ).scalars().all()
    assert len(rows) == 1


async def test_scheduler_records_sanitized_failed_audit_when_runner_fails(
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    await _enable_worker_config(db_session, tenant_id)
    lock = FakeLeaderLock(acquired=True)

    async def failing_run(**_kwargs):
        raise RuntimeError("Authorization: Bearer secret-scheduler-token")

    async def acquire_lock(_db):
        return lock

    report = await evaluate_dispatch_automation_workers_for_tenants(
        db_session,
        limit=10,
        run_func=failing_run,
        acquire_lock_func=acquire_lock,
    )

    assert report.lock_acquired is True
    assert report.lock_skipped is False
    assert report.tenants_scanned == 1
    assert report.tenants_enabled == 1
    assert report.tenants_due == 1
    assert report.failed_tenants == 1
    assert report.failed == 1
    assert "secret-scheduler-token" not in str(report)

    rows = (
        await db_session.execute(
            select(DispatchAutomationWorkerRun).where(
                DispatchAutomationWorkerRun.tenant_id == tenant_id,
                DispatchAutomationWorkerRun.trigger_type == "scheduled",
            )
        )
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].status == "failed"
    assert rows[0].failed == 1
    assert rows[0].error_message == "Authorization: **** ****"
    assert lock.released is True


async def test_scheduler_continues_past_disabled_tenants_to_fill_due_slots(
    registered_user,
    db_session,
):
    disabled_tenant_id = uuid.UUID(registered_user["tenant_id"])
    disabled_workflow, disabled_plan = await _create_approved_resume_plan(
        db_session,
        disabled_tenant_id,
    )
    due_tenant = await _create_tenant(
        db_session,
        slug=f"due-after-disabled-{uuid.uuid4()}",
        enabled=True,
        max_plans_per_run=1,
    )
    due_workflow, due_plan = await _create_approved_resume_plan(db_session, due_tenant.id)

    report = await evaluate_dispatch_automation_workers_for_tenants(db_session, limit=1)

    assert report.tenants_scanned == 2
    assert report.tenants_enabled == 1
    assert report.tenants_due == 1
    assert report.claimed == 1
    await db_session.refresh(disabled_workflow)
    await db_session.refresh(disabled_plan)
    await db_session.refresh(due_workflow)
    await db_session.refresh(due_plan)
    assert disabled_workflow.dispatch_paused is True
    assert disabled_plan.status == "approved"
    assert due_workflow.dispatch_paused is False
    assert due_plan.status == "executed"


async def test_scheduler_backoff_skips_failed_tenant_without_consuming_due_slot(
    registered_user,
    db_session,
):
    failed_tenant_id = uuid.UUID(registered_user["tenant_id"])
    await _enable_worker_config(db_session, failed_tenant_id, interval_minutes=5)
    failed_workflow, failed_plan = await _create_approved_resume_plan(
        db_session,
        failed_tenant_id,
    )
    db_session.add(
        DispatchAutomationWorkerRun(
            tenant_id=failed_tenant_id,
            trigger_type="scheduled",
            status="failed",
            limit=10,
            claimed=0,
            executed=0,
            blocked=0,
            failed=1,
            error_message="Authorization: **** ****",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=10),
        )
    )
    due_tenant = await _create_tenant(
        db_session,
        slug=f"due-after-backoff-{uuid.uuid4()}",
        enabled=True,
        interval_minutes=5,
        max_plans_per_run=1,
    )
    due_workflow, due_plan = await _create_approved_resume_plan(db_session, due_tenant.id)
    await db_session.commit()

    report = await evaluate_dispatch_automation_workers_for_tenants(db_session, limit=1)

    assert report.tenants_scanned == 2
    assert report.tenants_enabled == 2
    assert report.tenants_skipped_backoff == 1
    assert report.tenants_skipped_interval == 0
    assert report.tenants_due == 1
    assert report.claimed == 1
    await db_session.refresh(failed_workflow)
    await db_session.refresh(failed_plan)
    await db_session.refresh(due_workflow)
    await db_session.refresh(due_plan)
    assert failed_workflow.dispatch_paused is True
    assert failed_plan.status == "approved"
    assert due_workflow.dispatch_paused is False
    assert due_plan.status == "executed"


async def test_scheduler_fleet_snapshot_reports_readiness_without_mutation_or_secrets(
    registered_user,
    db_session,
):
    now = datetime(2026, 5, 28, 12, 0, tzinfo=timezone.utc)
    disabled_tenant_id = uuid.UUID(registered_user["tenant_id"])
    disabled_tenant = await db_session.get(Tenant, disabled_tenant_id)
    disabled_tenant.name = "Fleet Hidden Disabled Name"
    disabled_tenant.slug = f"fleet-hidden-disabled-{uuid.uuid4()}"
    disabled_tenant.dispatch_automation_worker_config = {
        "enabled": False,
        "interval_minutes": 15,
        "max_plans_per_run": 7,
    }
    db_session.add(disabled_tenant)
    disabled_workflow, disabled_plan = await _create_approved_resume_plan(
        db_session,
        disabled_tenant_id,
    )
    due_tenant = await _create_tenant(
        db_session,
        slug=f"fleet-hidden-due-{uuid.uuid4()}",
        created_at=now - timedelta(minutes=4),
        enabled=True,
        interval_minutes=10,
        max_plans_per_run=2,
    )
    due_workflow, due_plan = await _create_approved_resume_plan(db_session, due_tenant.id)
    interval_tenant = await _create_tenant(
        db_session,
        slug=f"fleet-hidden-interval-{uuid.uuid4()}",
        created_at=now - timedelta(minutes=3),
        enabled=True,
        interval_minutes=30,
        max_plans_per_run=3,
    )
    interval_workflow, interval_plan = await _create_approved_resume_plan(
        db_session,
        interval_tenant.id,
    )
    backoff_tenant = await _create_tenant(
        db_session,
        slug=f"fleet-hidden-backoff-{uuid.uuid4()}",
        created_at=now - timedelta(minutes=2),
        enabled=True,
        interval_minutes=5,
        max_plans_per_run=4,
    )
    backoff_workflow, backoff_plan = await _create_approved_resume_plan(
        db_session,
        backoff_tenant.id,
    )
    db_session.add_all(
        [
            DispatchAutomationWorkerRun(
                tenant_id=interval_tenant.id,
                trigger_type="scheduled",
                status="completed",
                limit=3,
                claimed=0,
                executed=0,
                blocked=0,
                failed=0,
                created_at=now - timedelta(minutes=5),
            ),
            DispatchAutomationWorkerRun(
                tenant_id=backoff_tenant.id,
                trigger_type="scheduled",
                status="failed",
                limit=4,
                claimed=0,
                executed=0,
                blocked=0,
                failed=1,
                error_message="Authorization: Bearer secret-fleet-token",
                created_at=now - timedelta(minutes=10),
            ),
        ]
    )
    await db_session.commit()
    audit_rows_before = await db_session.scalar(
        select(func.count(DispatchAutomationWorkerRun.id))
    )

    snapshot = await inspect_dispatch_automation_scheduler_fleet(
        db_session,
        scheduler_enabled=False,
        scheduler_interval_seconds=60.0,
        scheduler_tenant_limit=25,
        now=now,
    )

    assert snapshot.scheduler_enabled is False
    assert snapshot.scheduler_interval_seconds == 60.0
    assert snapshot.scheduler_tenant_limit == 25
    assert snapshot.total_tenants >= 4
    assert snapshot.configured_tenants >= 4
    assert snapshot.enabled_tenants >= 3
    assert snapshot.disabled_tenants >= 1
    assert snapshot.due_tenants >= 1
    assert snapshot.interval_waiting_tenants >= 1
    assert snapshot.backoff_tenants >= 1
    assert snapshot.approved_plan_backlog >= 4

    summaries = {summary.tenant_id: summary for summary in snapshot.tenants}
    disabled_summary = summaries[str(disabled_tenant_id)]
    due_summary = summaries[str(due_tenant.id)]
    interval_summary = summaries[str(interval_tenant.id)]
    backoff_summary = summaries[str(backoff_tenant.id)]
    assert disabled_summary.enabled is False
    assert disabled_summary.due_now is False
    assert disabled_summary.skip_reason == "tenant_disabled"
    assert due_summary.enabled is True
    assert due_summary.due_now is True
    assert due_summary.skip_reason is None
    assert due_summary.approved_plan_count == 1
    assert interval_summary.due_now is False
    assert interval_summary.skip_reason == "interval"
    assert interval_summary.latest_scheduled_status == "completed"
    assert interval_summary.next_run_at == now + timedelta(minutes=25)
    assert backoff_summary.due_now is False
    assert backoff_summary.skip_reason == "backoff"
    assert backoff_summary.latest_scheduled_status == "failed"
    assert backoff_summary.backoff_until == now + timedelta(minutes=20)
    assert backoff_summary.next_run_at == now + timedelta(minutes=20)

    snapshot_text = str(asdict(snapshot))
    assert "Fleet Hidden Disabled Name" not in snapshot_text
    assert "fleet-hidden" not in snapshot_text
    assert "owner@test.com" not in snapshot_text
    assert "secret-workflow-token" not in snapshot_text
    assert "secret-fleet-token" not in snapshot_text
    assert "Authorization" not in snapshot_text

    audit_rows_after = await db_session.scalar(
        select(func.count(DispatchAutomationWorkerRun.id))
    )
    assert audit_rows_after == audit_rows_before
    for workflow, plan in (
        (disabled_workflow, disabled_plan),
        (due_workflow, due_plan),
        (interval_workflow, interval_plan),
        (backoff_workflow, backoff_plan),
    ):
        await db_session.refresh(workflow)
        await db_session.refresh(plan)
        assert workflow.dispatch_paused is True
        assert plan.status == "approved"


async def test_scheduler_fleet_snapshot_can_omit_tenant_summaries_for_aggregate_only(
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    await _enable_worker_config(db_session, tenant_id, interval_minutes=10)
    await _create_approved_resume_plan(db_session, tenant_id)

    snapshot = await inspect_dispatch_automation_scheduler_fleet(
        db_session,
        scheduler_enabled=True,
        scheduler_interval_seconds=30.0,
        scheduler_tenant_limit=5,
        include_tenants=False,
    )

    assert snapshot.scheduler_enabled is True
    assert snapshot.total_tenants >= 1
    assert snapshot.enabled_tenants >= 1
    assert snapshot.approved_plan_backlog >= 1
    assert snapshot.tenants == []
