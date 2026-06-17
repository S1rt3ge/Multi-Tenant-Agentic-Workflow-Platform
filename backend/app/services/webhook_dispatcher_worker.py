"""Config-gated process worker for webhook dispatching."""

import asyncio
import logging
from collections.abc import Callable
from typing import Awaitable

from fastapi import FastAPI

from app.core.config import Settings
from app.services.webhook_dispatcher_service import (
    WebhookDispatchReport,
    dispatch_pending_webhook_executions,
)

logger = logging.getLogger(__name__)

DispatchFunc = Callable[..., Awaitable[WebhookDispatchReport | None]]


class WebhookDispatcherWorker:
    """Small in-process loop that dispatches pending webhook executions.

    The worker intentionally depends on a session factory and a dispatch
    function so it can be tested without opening real network or queue
    dependencies.
    """

    def __init__(
        self,
        session_factory,
        interval_seconds: float,
        batch_limit: int,
        dispatch_func: DispatchFunc = dispatch_pending_webhook_executions,
    ):
        self.session_factory = session_factory
        self.interval_seconds = max(float(interval_seconds), 0.01)
        self.batch_limit = max(int(batch_limit), 1)
        self.dispatch_func = dispatch_func
        self._task: asyncio.Task | None = None
        self._stop_event = asyncio.Event()

    @property
    def is_running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def run_once(self) -> WebhookDispatchReport | None:
        async with self.session_factory() as db:
            return await self.dispatch_func(db, limit=self.batch_limit)

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
                if report and report.dispatched:
                    logger.info(
                        "webhook_dispatcher_worker_dispatched",
                        extra={
                            "dispatched": report.dispatched,
                            "scanned": report.scanned,
                            "skipped": report.skipped,
                        },
                    )
            except Exception:
                logger.exception("webhook_dispatcher_worker_error")

            try:
                await asyncio.wait_for(
                    self._stop_event.wait(),
                    timeout=self.interval_seconds,
                )
            except TimeoutError:
                continue


def install_webhook_dispatcher_worker(app: FastAPI, settings: Settings) -> None:
    """Install startup/shutdown hooks when the worker is enabled."""
    if not settings.WEBHOOK_DISPATCHER_ENABLED:
        app.state.webhook_dispatcher_worker = None
        return

    worker = WebhookDispatcherWorker(
        session_factory=app.state.db_session_factory,
        interval_seconds=settings.WEBHOOK_DISPATCHER_INTERVAL_SECONDS,
        batch_limit=settings.WEBHOOK_DISPATCHER_BATCH_LIMIT,
    )
    app.state.webhook_dispatcher_worker = worker

    async def _start_webhook_dispatcher_worker() -> None:
        worker.start()

    async def _stop_webhook_dispatcher_worker() -> None:
        await worker.stop()

    app.router.add_event_handler("startup", _start_webhook_dispatcher_worker)
    app.router.add_event_handler("shutdown", _stop_webhook_dispatcher_worker)
