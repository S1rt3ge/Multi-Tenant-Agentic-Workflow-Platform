"""Config-gated scheduled execution for dispatch automation plans."""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from fastapi import FastAPI
from sqlalchemy import func, select, text

from app.core.config import Settings
from app.models.dispatch_alert import DispatchAutomationPlan, DispatchAutomationWorkerRun
from app.models.tenant import Tenant
from app.services import analytics_service
from app.services.dispatch_automation_plan_worker import (
    DispatchAutomationWorkerResult,
    run_dispatch_automation_plan_worker_once,
)

logger = logging.getLogger(__name__)

AutomationRunFunc = Callable[..., Awaitable[DispatchAutomationWorkerResult | None]]
DISPATCH_AUTOMATION_SCHEDULER_LOCK_KEY = 912021
FAILED_RUN_BACKOFF_MINUTES = 30


@dataclass
class SchedulerLeaderLock:
    acquired: bool
    release_func: Callable[[], Awaitable[None]] | None = None

    async def release(self) -> None:
        if self.release_func is not None:
            await self.release_func()


async def acquire_dispatch_automation_scheduler_lock(db) -> SchedulerLeaderLock:
    """Acquire the scheduler leader lock.

    PostgreSQL gets a real advisory lock. Local SQLite tests fall back to an
    acquired no-op lock because they run in one process and cannot use PG locks.
    """
    bind = db.get_bind() if hasattr(db, "get_bind") else getattr(db, "bind", None)
    dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
    if dialect_name != "postgresql":
        return SchedulerLeaderLock(acquired=True)

    result = await db.execute(
        text("SELECT pg_try_advisory_lock(:lock_key)"),
        {"lock_key": DISPATCH_AUTOMATION_SCHEDULER_LOCK_KEY},
    )
    acquired = bool(result.scalar())
    if not acquired:
        return SchedulerLeaderLock(acquired=False)

    async def _release() -> None:
        await db.execute(
            text("SELECT pg_advisory_unlock(:lock_key)"),
            {"lock_key": DISPATCH_AUTOMATION_SCHEDULER_LOCK_KEY},
        )

    return SchedulerLeaderLock(acquired=True, release_func=_release)


@dataclass
class DispatchAutomationSchedulerReport:
    lock_acquired: bool = True
    lock_skipped: bool = False
    tenants_scanned: int = 0
    tenants_enabled: int = 0
    tenants_due: int = 0
    tenants_skipped_interval: int = 0
    tenants_skipped_backoff: int = 0
    failed_tenants: int = 0
    claimed: int = 0
    executed: int = 0
    blocked: int = 0
    failed: int = 0
    tenant_ids: list[str] = field(default_factory=list)

    def add_result(self, tenant_id, result: DispatchAutomationWorkerResult) -> None:
        self.tenants_due += 1
        self.tenant_ids.append(str(tenant_id))
        self.claimed += result.claimed
        self.executed += result.executed
        self.blocked += result.blocked
        self.failed += result.failed

    def add_failure(self, tenant_id) -> None:
        self.tenants_due += 1
        self.failed_tenants += 1
        self.failed += 1
        self.tenant_ids.append(str(tenant_id))


@dataclass
class DispatchAutomationTenantReadinessSummary:
    tenant_id: str
    enabled: bool
    due_now: bool
    skip_reason: str | None
    approved_plan_count: int
    latest_scheduled_status: str | None = None
    last_scheduled_at: datetime | None = None
    next_run_at: datetime | None = None
    backoff_until: datetime | None = None
    max_plans_per_run: int = 10


@dataclass
class DispatchAutomationSchedulerFleetSnapshot:
    generated_at: datetime
    scheduler_enabled: bool
    scheduler_interval_seconds: float
    scheduler_tenant_limit: int
    total_tenants: int = 0
    configured_tenants: int = 0
    enabled_tenants: int = 0
    disabled_tenants: int = 0
    due_tenants: int = 0
    interval_waiting_tenants: int = 0
    backoff_tenants: int = 0
    approved_plan_backlog: int = 0
    tenants: list[DispatchAutomationTenantReadinessSummary] = field(
        default_factory=list
    )


@dataclass(frozen=True)
class _TenantScheduleDueState:
    due_now: bool
    skip_reason: str | None
    next_run_at: datetime | None = None
    backoff_until: datetime | None = None


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


async def _latest_scheduled_run(
    db,
    tenant_id,
) -> DispatchAutomationWorkerRun | None:
    result = await db.execute(
        select(DispatchAutomationWorkerRun)
        .where(
            DispatchAutomationWorkerRun.tenant_id == tenant_id,
            DispatchAutomationWorkerRun.trigger_type == "scheduled",
        )
        .order_by(DispatchAutomationWorkerRun.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


def _tenant_schedule_due_state(
    *,
    enabled: bool,
    interval_minutes: int,
    latest_run: DispatchAutomationWorkerRun | None,
    now: datetime,
) -> _TenantScheduleDueState:
    if not enabled:
        return _TenantScheduleDueState(
            due_now=False,
            skip_reason="tenant_disabled",
        )
    if latest_run is None or latest_run.created_at is None:
        return _TenantScheduleDueState(due_now=True, skip_reason=None)

    last_run_at = _ensure_utc(latest_run.created_at)
    effective_interval = interval_minutes
    if latest_run.status == "failed":
        effective_interval = max(interval_minutes, FAILED_RUN_BACKOFF_MINUTES)
    next_run_at = last_run_at + timedelta(minutes=effective_interval)
    if now >= next_run_at:
        return _TenantScheduleDueState(
            due_now=True,
            skip_reason=None,
            backoff_until=next_run_at if latest_run.status == "failed" else None,
        )
    if latest_run.status == "failed":
        return _TenantScheduleDueState(
            due_now=False,
            skip_reason="backoff",
            next_run_at=next_run_at,
            backoff_until=next_run_at,
        )
    return _TenantScheduleDueState(
        due_now=False,
        skip_reason="interval",
        next_run_at=next_run_at,
    )


async def _tenant_schedule_is_due(
    db,
    tenant_id,
    interval_minutes: int,
    now: datetime,
) -> str | None:
    latest_run = await _latest_scheduled_run(db, tenant_id)
    return _tenant_schedule_due_state(
        enabled=True,
        interval_minutes=interval_minutes,
        latest_run=latest_run,
        now=now,
    ).skip_reason


async def inspect_dispatch_automation_scheduler_fleet(
    db,
    *,
    scheduler_enabled: bool,
    scheduler_interval_seconds: float,
    scheduler_tenant_limit: int,
    now: datetime | None = None,
    include_tenants: bool = True,
) -> DispatchAutomationSchedulerFleetSnapshot:
    """Return a sanitized read-only fleet snapshot for scheduler operations."""
    current_time = _ensure_utc(now or datetime.now(timezone.utc))
    tenant_result = await db.execute(select(Tenant).order_by(Tenant.created_at.asc()))
    tenants = tenant_result.scalars().all()
    plan_count_result = await db.execute(
        select(
            DispatchAutomationPlan.tenant_id,
            func.count(DispatchAutomationPlan.id),
        )
        .where(DispatchAutomationPlan.status == "approved")
        .group_by(DispatchAutomationPlan.tenant_id)
    )
    approved_plan_counts = {
        str(tenant_id): int(approved_count or 0)
        for tenant_id, approved_count in plan_count_result.all()
    }
    snapshot = DispatchAutomationSchedulerFleetSnapshot(
        generated_at=current_time,
        scheduler_enabled=bool(scheduler_enabled),
        scheduler_interval_seconds=float(scheduler_interval_seconds),
        scheduler_tenant_limit=max(int(scheduler_tenant_limit), 1),
        total_tenants=len(tenants),
    )

    for tenant in tenants:
        tenant_key = str(tenant.id)
        config = await analytics_service.get_dispatch_automation_worker_config(
            db,
            tenant.id,
        )
        latest_run = await _latest_scheduled_run(db, tenant.id)
        approved_plan_count = approved_plan_counts.get(tenant_key, 0)
        due_state = _tenant_schedule_due_state(
            enabled=config.enabled,
            interval_minutes=config.interval_minutes,
            latest_run=latest_run,
            now=current_time,
        )

        snapshot.approved_plan_backlog += approved_plan_count
        if tenant.dispatch_automation_worker_config:
            snapshot.configured_tenants += 1
        if config.enabled:
            snapshot.enabled_tenants += 1
        else:
            snapshot.disabled_tenants += 1
        if due_state.due_now:
            snapshot.due_tenants += 1
        elif due_state.skip_reason == "interval":
            snapshot.interval_waiting_tenants += 1
        elif due_state.skip_reason == "backoff":
            snapshot.backoff_tenants += 1

        if include_tenants:
            last_scheduled_at = (
                _ensure_utc(latest_run.created_at)
                if latest_run is not None and latest_run.created_at is not None
                else None
            )
            snapshot.tenants.append(
                DispatchAutomationTenantReadinessSummary(
                    tenant_id=tenant_key,
                    enabled=config.enabled,
                    due_now=due_state.due_now,
                    skip_reason=due_state.skip_reason,
                    approved_plan_count=approved_plan_count,
                    latest_scheduled_status=(
                        latest_run.status if latest_run is not None else None
                    ),
                    last_scheduled_at=last_scheduled_at,
                    next_run_at=due_state.next_run_at,
                    backoff_until=due_state.backoff_until,
                    max_plans_per_run=config.max_plans_per_run,
                )
            )

    return snapshot


async def evaluate_dispatch_automation_workers_for_tenants(
    db,
    limit: int = 25,
    now: datetime | None = None,
    run_func: AutomationRunFunc = run_dispatch_automation_plan_worker_once,
    acquire_lock_func: Callable[..., Awaitable[SchedulerLeaderLock]] = (
        acquire_dispatch_automation_scheduler_lock
    ),
) -> DispatchAutomationSchedulerReport:
    """Run due tenant automation worker configs and write scheduled audit rows."""
    tenant_limit = max(int(limit), 1)
    current_time = _ensure_utc(now or datetime.now(timezone.utc))
    lock = await acquire_lock_func(db)
    if not lock.acquired:
        return DispatchAutomationSchedulerReport(lock_acquired=False, lock_skipped=True)

    try:
        result = await db.execute(select(Tenant).order_by(Tenant.created_at.asc()))
        tenants = result.scalars().all()
        report = DispatchAutomationSchedulerReport()

        for tenant in tenants:
            if report.tenants_due >= tenant_limit:
                break
            report.tenants_scanned += 1
            config = await analytics_service.get_dispatch_automation_worker_config(db, tenant.id)
            if not config.enabled:
                continue
            report.tenants_enabled += 1

            skip_reason = await _tenant_schedule_is_due(
                db=db,
                tenant_id=tenant.id,
                interval_minutes=config.interval_minutes,
                now=current_time,
            )
            if skip_reason == "interval":
                report.tenants_skipped_interval += 1
                continue
            if skip_reason == "backoff":
                report.tenants_skipped_backoff += 1
                continue

            try:
                run_result = await run_func(
                    db=db,
                    limit=config.max_plans_per_run,
                    tenant_id=tenant.id,
                )
                if run_result is None:
                    run_result = DispatchAutomationWorkerResult()
                await analytics_service.record_dispatch_automation_worker_run(
                    db=db,
                    tenant_id=tenant.id,
                    trigger_type="scheduled",
                    run_limit=config.max_plans_per_run,
                    claimed=run_result.claimed,
                    executed=run_result.executed,
                    blocked=run_result.blocked,
                    failed=run_result.failed,
                )
                report.add_result(tenant.id, run_result)
            except Exception as exc:
                await analytics_service.record_dispatch_automation_worker_run(
                    db=db,
                    tenant_id=tenant.id,
                    trigger_type="scheduled",
                    run_limit=config.max_plans_per_run,
                    claimed=0,
                    executed=0,
                    blocked=0,
                    failed=1,
                    run_status="failed",
                    error_message=str(exc),
                )
                report.add_failure(tenant.id)

        return report
    finally:
        try:
            await lock.release()
        except Exception:
            logger.exception(
                "dispatch_automation_worker_scheduler_lock_release_error"
            )


EvaluateFunc = Callable[..., Awaitable[DispatchAutomationSchedulerReport | None]]


class DispatchAutomationWorkerScheduler:
    """Small in-process loop that executes due dispatch automation worker configs."""

    def __init__(
        self,
        session_factory,
        interval_seconds: float,
        tenant_limit: int,
        evaluate_func: EvaluateFunc = evaluate_dispatch_automation_workers_for_tenants,
    ):
        self.session_factory = session_factory
        self.interval_seconds = max(float(interval_seconds), 0.01)
        self.tenant_limit = max(int(tenant_limit), 1)
        self.evaluate_func = evaluate_func
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def run_once(self) -> DispatchAutomationSchedulerReport | None:
        async with self.session_factory() as db:
            return await self.evaluate_func(db, limit=self.tenant_limit)

    def start(self) -> None:
        if self.is_running:
            return
        self._stop_event = asyncio.Event()
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        self._stop_event.set()
        if self._task is None:
            return
        await self._task
        self._task = None

    async def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                report = await self.run_once()
                if report and (report.claimed or report.failed_tenants):
                    logger.info(
                        "dispatch_automation_worker_scheduler_evaluated",
                        extra={
                            "tenants_enabled": report.tenants_enabled,
                            "tenants_due": report.tenants_due,
                            "tenants_skipped_interval": report.tenants_skipped_interval,
                            "tenants_skipped_backoff": report.tenants_skipped_backoff,
                            "failed_tenants": report.failed_tenants,
                            "claimed": report.claimed,
                            "executed": report.executed,
                            "blocked": report.blocked,
                            "failed": report.failed,
                        },
                    )
            except Exception:
                logger.exception("dispatch_automation_worker_scheduler_error")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.interval_seconds,
                )
            except TimeoutError:
                continue


def install_dispatch_automation_worker_scheduler(app: FastAPI, settings: Settings) -> None:
    """Install startup/shutdown hooks when the automation scheduler is enabled."""
    if not settings.DISPATCH_AUTOMATION_WORKER_ENABLED:
        app.state.dispatch_automation_worker_scheduler = None
        return

    worker = DispatchAutomationWorkerScheduler(
        session_factory=app.state.db_session_factory,
        interval_seconds=settings.DISPATCH_AUTOMATION_WORKER_INTERVAL_SECONDS,
        tenant_limit=settings.DISPATCH_AUTOMATION_WORKER_TENANT_LIMIT,
    )
    app.state.dispatch_automation_worker_scheduler = worker

    async def _start_dispatch_automation_worker_scheduler() -> None:
        worker.start()

    async def _stop_dispatch_automation_worker_scheduler() -> None:
        await worker.stop()

    app.router.add_event_handler("startup", _start_dispatch_automation_worker_scheduler)
    app.router.add_event_handler("shutdown", _stop_dispatch_automation_worker_scheduler)
