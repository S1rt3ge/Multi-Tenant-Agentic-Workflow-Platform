"""Config-gated scheduled evaluation for dispatch alert policies."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Awaitable

from fastapi import FastAPI
from sqlalchemy import select

from app.core.config import Settings
from app.models.tenant import Tenant
from app.schemas.analytics import DispatchAlertDeliveryResponse
from app.services import analytics_service

logger = logging.getLogger(__name__)


@dataclass
class DispatchAlertEvaluationReport:
    tenants_scanned: int = 0
    tenants_evaluated: int = 0
    attempted: int = 0
    delivered: int = 0
    failed: int = 0
    skipped: int = 0
    tenant_ids: list[str] = field(default_factory=list)

    def add_delivery(self, tenant_id, delivery: DispatchAlertDeliveryResponse) -> None:
        self.tenants_evaluated += 1
        self.tenant_ids.append(str(tenant_id))
        self.attempted += delivery.attempted
        self.delivered += delivery.delivered
        self.failed += delivery.failed
        self.skipped += delivery.skipped


async def evaluate_dispatch_alerts_for_tenants(
    db,
    limit: int = 25,
    window_hours: int = 24,
) -> DispatchAlertEvaluationReport:
    """Evaluate enabled tenant alert policies and deliver eligible alerts."""
    tenant_limit = max(int(limit), 1)
    result = await db.execute(
        select(Tenant)
        .order_by(Tenant.created_at.asc())
        .limit(tenant_limit)
    )
    tenants = result.scalars().all()
    report = DispatchAlertEvaluationReport(tenants_scanned=len(tenants))

    for tenant in tenants:
        policy = await analytics_service.get_dispatch_alert_policy(db, tenant.id)
        if not policy.enabled or not policy.channels:
            continue

        delivery = await analytics_service.deliver_dispatch_alerts(
            db=db,
            tenant_id=tenant.id,
            window_hours=window_hours,
            enforce_cooldown=True,
        )
        report.add_delivery(tenant.id, delivery)

    return report


EvaluateFunc = Callable[..., Awaitable[DispatchAlertEvaluationReport | None]]


class DispatchAlertEvaluationWorker:
    """Small in-process loop that evaluates dispatch alert policies."""

    def __init__(
        self,
        session_factory,
        interval_seconds: float,
        tenant_limit: int,
        window_hours: int,
        evaluate_func: EvaluateFunc = evaluate_dispatch_alerts_for_tenants,
    ):
        self.session_factory = session_factory
        self.interval_seconds = max(float(interval_seconds), 0.01)
        self.tenant_limit = max(int(tenant_limit), 1)
        self.window_hours = max(int(window_hours), 1)
        self.evaluate_func = evaluate_func
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def run_once(self) -> DispatchAlertEvaluationReport | None:
        async with self.session_factory() as db:
            return await self.evaluate_func(
                db,
                limit=self.tenant_limit,
                window_hours=self.window_hours,
            )

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
                if report and (report.attempted or report.skipped):
                    logger.info(
                        "dispatch_alert_evaluator_worker_evaluated",
                        extra={
                            "tenants_evaluated": report.tenants_evaluated,
                            "attempted": report.attempted,
                            "delivered": report.delivered,
                            "failed": report.failed,
                            "skipped": report.skipped,
                        },
                    )
            except Exception:
                logger.exception("dispatch_alert_evaluator_worker_error")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.interval_seconds,
                )
            except TimeoutError:
                continue


def install_dispatch_alert_evaluator_worker(app: FastAPI, settings: Settings) -> None:
    """Install startup/shutdown hooks when the alert evaluator is enabled."""
    if not settings.DISPATCH_ALERT_EVALUATOR_ENABLED:
        app.state.dispatch_alert_evaluator_worker = None
        return

    worker = DispatchAlertEvaluationWorker(
        session_factory=app.state.db_session_factory,
        interval_seconds=settings.DISPATCH_ALERT_EVALUATOR_INTERVAL_SECONDS,
        tenant_limit=settings.DISPATCH_ALERT_EVALUATOR_TENANT_LIMIT,
        window_hours=settings.DISPATCH_ALERT_EVALUATOR_WINDOW_HOURS,
    )
    app.state.dispatch_alert_evaluator_worker = worker

    async def _start_dispatch_alert_evaluator_worker() -> None:
        worker.start()

    async def _stop_dispatch_alert_evaluator_worker() -> None:
        await worker.stop()

    app.router.add_event_handler("startup", _start_dispatch_alert_evaluator_worker)
    app.router.add_event_handler("shutdown", _stop_dispatch_alert_evaluator_worker)
