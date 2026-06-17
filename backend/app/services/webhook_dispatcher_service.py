"""Webhook execution dispatcher service.

M11 keeps webhook ingestion durable: the public webhook endpoint creates a
pending execution, while this internal service is responsible for finding and
running webhook-triggered pending executions.
"""

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.executor import run_execution
from app.models.execution import Execution, ExecutionLog
from app.models.workflow import Workflow


DEFAULT_DISPATCH_LIMIT = 10
PENDING_SCAN_LIMIT = 100


@dataclass(slots=True)
class WebhookDispatchReport:
    scanned: int = 0
    dispatched: int = 0
    skipped: int = 0
    deferred: int = 0
    paused: int = 0
    retries_scheduled: int = 0
    dead_lettered: int = 0
    execution_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class WebhookRetryPolicy:
    max_attempts: int = 3
    backoff_seconds: int = 60


def is_webhook_trigger_execution(execution: Execution) -> bool:
    input_data = execution.input_data if isinstance(execution.input_data, dict) else {}
    trigger = input_data.get("trigger")
    if not isinstance(trigger, dict):
        return False
    return trigger.get("type") == "webhook"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _dispatch_metadata(input_data: dict) -> dict:
    metadata = input_data.get("dispatch")
    return metadata if isinstance(metadata, dict) else {}


def _attempt_number(input_data: dict) -> int:
    value = _dispatch_metadata(input_data).get("attempt", 1)
    try:
        return max(int(value), 1)
    except (TypeError, ValueError):
        return 1


def _parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _is_retry_due(execution: Execution, now: datetime) -> bool:
    input_data = execution.input_data if isinstance(execution.input_data, dict) else {}
    next_attempt_at = _parse_datetime(
        _dispatch_metadata(input_data).get("next_attempt_at")
    )
    return next_attempt_at is None or next_attempt_at <= now


def _supports_skip_locked(db: AsyncSession) -> bool:
    try:
        return db.get_bind().dialect.name == "postgresql"
    except Exception:
        return False


async def _pending_execution_candidates(
    db: AsyncSession,
    scan_limit: int,
) -> list[Execution]:
    stmt = (
        select(Execution)
        .where(Execution.status == "pending")
        .order_by(Execution.created_at, Execution.id)
        .limit(scan_limit)
    )
    # On Postgres, lock the candidate rows and skip ones another dispatcher
    # instance already holds, preventing the same pending execution from being
    # picked up twice when more than one worker runs. (No-op on SQLite tests.)
    if _supports_skip_locked(db):
        stmt = stmt.with_for_update(skip_locked=True)
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def _has_retryable_failure(db: AsyncSession, execution_id) -> bool:
    result = await db.execute(
        select(ExecutionLog.id)
        .where(
            ExecutionLog.execution_id == execution_id,
            ExecutionLog.retryable == True,  # noqa: E712
        )
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


async def _is_workflow_dispatch_paused(db: AsyncSession, workflow_id) -> bool:
    result = await db.execute(
        select(Workflow.dispatch_paused).where(Workflow.id == workflow_id)
    )
    return result.scalar_one_or_none() is True


def _with_dispatch_metadata(input_data: dict, metadata: dict) -> dict:
    next_input = deepcopy(input_data)
    next_input["dispatch"] = metadata
    return next_input


async def _schedule_retry_execution(
    db: AsyncSession,
    execution: Execution,
    policy: WebhookRetryPolicy,
    now: datetime,
) -> Execution:
    input_data = execution.input_data if isinstance(execution.input_data, dict) else {}
    current_metadata = _dispatch_metadata(input_data)
    next_attempt_at = now + timedelta(seconds=policy.backoff_seconds)
    next_metadata = {
        **current_metadata,
        "attempt": _attempt_number(input_data) + 1,
        "root_execution_id": current_metadata.get("root_execution_id") or str(execution.id),
        "parent_execution_id": str(execution.id),
        "previous_execution_id": str(execution.id),
        "next_attempt_at": next_attempt_at.isoformat(),
        "dead_lettered": False,
    }
    retry_execution = Execution(
        tenant_id=execution.tenant_id,
        workflow_id=execution.workflow_id,
        status="pending",
        input_data=_with_dispatch_metadata(input_data, next_metadata),
    )
    db.add(retry_execution)
    await db.commit()
    await db.refresh(retry_execution)
    return retry_execution


async def _mark_dead_lettered(
    db: AsyncSession,
    execution: Execution,
    now: datetime,
) -> None:
    input_data = execution.input_data if isinstance(execution.input_data, dict) else {}
    metadata = {
        **_dispatch_metadata(input_data),
        "attempt": _attempt_number(input_data),
        "dead_lettered": True,
        "dead_letter_reason": "max_attempts_exhausted",
        "dead_lettered_at": now.isoformat(),
    }
    await db.execute(
        update(Execution)
        .where(Execution.id == execution.id)
        .values(input_data=_with_dispatch_metadata(input_data, metadata))
    )
    await db.commit()


async def _apply_retry_policy_after_dispatch(
    db: AsyncSession,
    execution_id,
    policy: WebhookRetryPolicy,
    now: datetime,
) -> str | None:
    execution = await db.get(Execution, execution_id)
    if execution is None or execution.status != "failed":
        return None
    if not await _has_retryable_failure(db, execution.id):
        return None

    input_data = execution.input_data if isinstance(execution.input_data, dict) else {}
    if _attempt_number(input_data) >= policy.max_attempts:
        await _mark_dead_lettered(db, execution, now)
        return "dead_lettered"

    await _schedule_retry_execution(db, execution, policy, now)
    return "retry_scheduled"


async def dispatch_pending_webhook_executions(
    db: AsyncSession,
    limit: int = DEFAULT_DISPATCH_LIMIT,
    retry_policy: WebhookRetryPolicy | None = None,
    now: datetime | None = None,
) -> WebhookDispatchReport:
    """Dispatch pending webhook-triggered executions through the executor.

    This is intentionally a service, not a public route. A later worker loop can
    call the same function on an interval or from a queue consumer.
    """
    if limit <= 0:
        return WebhookDispatchReport()

    report = WebhookDispatchReport()
    effective_policy = retry_policy or WebhookRetryPolicy()
    effective_now = now or _utc_now()
    scan_limit = max(PENDING_SCAN_LIMIT, limit)
    candidates = await _pending_execution_candidates(db, scan_limit=scan_limit)

    for execution in candidates:
        if report.dispatched >= limit:
            break

        report.scanned += 1
        if not is_webhook_trigger_execution(execution):
            report.skipped += 1
            continue
        if await _is_workflow_dispatch_paused(db, execution.workflow_id):
            report.paused += 1
            continue
        if not _is_retry_due(execution, effective_now):
            report.deferred += 1
            continue

        await run_execution(
            execution_id=execution.id,
            workflow_id=execution.workflow_id,
            tenant_id=execution.tenant_id,
            input_data=execution.input_data,
            db=db,
        )
        report.dispatched += 1
        report.execution_ids.append(str(execution.id))
        retry_result = await _apply_retry_policy_after_dispatch(
            db,
            execution.id,
            effective_policy,
            effective_now,
        )
        if retry_result == "retry_scheduled":
            report.retries_scheduled += 1
        elif retry_result == "dead_lettered":
            report.dead_lettered += 1

    return report
