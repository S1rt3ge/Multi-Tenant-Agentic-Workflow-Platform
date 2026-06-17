"""
Analytics service — M6 Dashboard.

Aggregates data from executions and execution_logs tables.
No new models required — pure SQL aggregation.

Business rules:
- All queries filtered by tenant_id from JWT.
- success_rate = completed / total * 100. If total == 0 → None ("N/A").
- Cost timeline fills missing days with zeros (no gaps on chart).
- Export: CSV or JSON. Streaming for large datasets. Max 50 000 rows.
- Server-side cache: 60 seconds (simple dict cache, invalidated on new execution).
"""

from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from urllib.parse import urlparse

from fastapi import HTTPException, status
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dispatch_alert import (
    DispatchAlertChannelCredential,
    DispatchAlertDelivery,
    DispatchAutomationPlan,
    DispatchAutomationWorkerRun,
    DispatchIncidentAcknowledgement,
)
from app.models.execution import Execution
from app.models.tenant import Tenant
from app.models.user import User
from app.models.workflow import Workflow
from app.models.connector import WebhookEvent, WorkflowTrigger
from app.schemas.analytics import (
    DispatchAlertChannelCredentialCreate,
    DispatchAlertChannelCredentialListResponse,
    DispatchAlertChannelCredentialResponse,
    OverviewResponse,
    CostTimelineItem,
    DispatchAlertPolicy,
    DispatchAlertPolicyPreview,
    DispatchAlertPolicyPreviewRoute,
    DispatchAlertDeliveryListResponse,
    DispatchAlertDeliveryResponse,
    DispatchAlertDeliveryItem,
    DispatchAutomationPlanCreate,
    DispatchAutomationPlanListResponse,
    DispatchAutomationPlanReject,
    DispatchAutomationPlanResponse,
    DispatchAutomationWorkerConfig,
    DispatchAutomationWorkerDiagnosticsResponse,
    DispatchAutomationWorkerRunListResponse,
    DispatchAutomationWorkerRunItem,
    DispatchAutomationRecommendation,
    DispatchControlRecommendationsResponse,
    DispatchIncidentAcknowledgementCreate,
    DispatchIncidentAcknowledgementResponse,
    DispatchIncidentAcknowledgementState,
    DispatchIncidentAnalyticsResponse,
    DispatchIncidentSeverityBreakdownItem,
    DispatchIncidentHistoryResponse,
    DispatchIncidentResolutionCreate,
    DispatchIncidentTrendItem,
    DispatchHealthAlert,
    DispatchHealthResponse,
    DispatchRunbookAction,
    DispatchRunbookPolicy,
    DispatchRunbookResponse,
    WorkflowBreakdownItem,
    ExportRow,
)
from app.services.connector_security import (
    decrypt_config,
    encrypt_config,
    redact_secret_values,
    sanitize_error,
)

DISPATCH_AUTOMATION_FAILED_RUN_BACKOFF_MINUTES = 30

# ---------------------------------------------------------------------------
# Simple in-memory cache (per-tenant, 60 sec TTL)
# ---------------------------------------------------------------------------

_cache: dict[str, tuple[float, object]] = {}
_CACHE_TTL = 60.0  # seconds


def _cache_key(tenant_id: uuid.UUID, prefix: str, **kwargs) -> str:
    parts = [prefix, str(tenant_id)]
    for k, v in sorted(kwargs.items()):
        parts.append(f"{k}={v}")
    return ":".join(parts)


def _get_cached(key: str):
    if key in _cache:
        ts, value = _cache[key]
        if (datetime.now(timezone.utc).timestamp() - ts) < _CACHE_TTL:
            return value
        del _cache[key]
    return None


def _set_cached(key: str, value):
    _cache[key] = (datetime.now(timezone.utc).timestamp(), value)


def invalidate_tenant_cache(tenant_id: uuid.UUID):
    """Called when a new execution is created to invalidate analytics cache."""
    tenant_key = str(tenant_id)
    keys_to_delete = [
        k for k in _cache if len(k.split(":")) > 1 and k.split(":")[1] == tenant_key
    ]
    for k in keys_to_delete:
        del _cache[k]


# ---------------------------------------------------------------------------
# Overview KPI
# ---------------------------------------------------------------------------

async def get_overview(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    period: str = "month",
) -> OverviewResponse:
    """
    KPI for the current period (default: current month).
    Returns total_executions, successful, failed, tokens_used, total_cost, success_rate.
    """
    cache_key = _cache_key(tenant_id, "overview", period=period)
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    # Period start date
    now = datetime.now(timezone.utc)
    if period == "month":
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        period_start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    else:
        # Default to month
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    stmt = select(
        func.count().label("total_executions"),
        func.count().filter(Execution.status == "completed").label("successful"),
        func.count().filter(Execution.status == "failed").label("failed"),
        func.coalesce(func.sum(Execution.total_tokens), 0).label("tokens_used"),
        func.coalesce(func.sum(Execution.total_cost), 0.0).label("total_cost"),
    ).where(
        and_(
            Execution.tenant_id == tenant_id,
            Execution.created_at >= period_start,
        )
    )

    result = await db.execute(stmt)
    row = result.one()

    total = row.total_executions
    successful = row.successful
    success_rate = round((successful / total) * 100, 1) if total > 0 else None

    response = OverviewResponse(
        total_executions=total,
        successful=successful,
        failed=row.failed,
        tokens_used=row.tokens_used,
        total_cost=round(row.total_cost, 4),
        success_rate=success_rate,
    )
    _set_cached(cache_key, response)
    return response


# ---------------------------------------------------------------------------
# Cost Timeline (last N days)
# ---------------------------------------------------------------------------

async def get_cost_timeline(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    days: int = 30,
) -> list[CostTimelineItem]:
    """
    Daily cost + execution count for the last N days.
    Missing days are filled with zeros.
    """
    cache_key = _cache_key(tenant_id, "cost_timeline", days=days)
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    now = datetime.now(timezone.utc)
    start_date = (now - timedelta(days=days - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0
    )

    # For SQLite compatibility, cast created_at to date via func.date()
    day_col = func.date(Execution.created_at).label("day")

    stmt = (
        select(
            day_col,
            func.coalesce(func.sum(Execution.total_cost), 0.0).label("daily_cost"),
            func.count().label("executions_count"),
        )
        .where(
            and_(
                Execution.tenant_id == tenant_id,
                Execution.created_at >= start_date,
            )
        )
        .group_by("day")
        .order_by("day")
    )

    result = await db.execute(stmt)
    rows = result.all()

    # Build a map of existing data
    data_map: dict[str, tuple[float, int]] = {}
    for row in rows:
        day_str = str(row.day)[:10]  # "YYYY-MM-DD"
        data_map[day_str] = (float(row.daily_cost), int(row.executions_count))

    # Fill missing days with zeros
    timeline: list[CostTimelineItem] = []
    current = start_date
    end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    while current <= end:
        day_str = current.strftime("%Y-%m-%d")
        cost, count = data_map.get(day_str, (0.0, 0))
        timeline.append(
            CostTimelineItem(
                day=day_str,
                daily_cost=round(cost, 4),
                executions_count=count,
            )
        )
        current += timedelta(days=1)

    _set_cached(cache_key, timeline)
    return timeline


# ---------------------------------------------------------------------------
# Workflow Breakdown
# ---------------------------------------------------------------------------

async def get_workflow_breakdown(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    period: str = "month",
) -> list[WorkflowBreakdownItem]:
    """
    Per-workflow breakdown: runs, cost, avg_duration, % of total cost.
    Sorted by cost descending.
    """
    cache_key = _cache_key(tenant_id, "workflow_breakdown", period=period)
    cached = _get_cached(cache_key)
    if cached is not None:
        return cached

    now = datetime.now(timezone.utc)
    if period == "month":
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "week":
        period_start = (now - timedelta(days=now.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
    else:
        period_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    # For duration calculation, we use (completed_at - started_at) in seconds.
    # SQLite doesn't support EXTRACT(EPOCH FROM ...), so we calculate differently.
    # We'll use a subquery approach that works on both PostgreSQL and SQLite.
    stmt = (
        select(
            Workflow.id.label("workflow_id"),
            Workflow.name.label("workflow_name"),
            func.count(Execution.id).label("runs"),
            func.coalesce(func.sum(Execution.total_cost), 0.0).label("cost"),
        )
        .join(Workflow, Execution.workflow_id == Workflow.id)
        .where(
            and_(
                Execution.tenant_id == tenant_id,
                Execution.created_at >= period_start,
            )
        )
        .group_by(Workflow.id, Workflow.name)
        .order_by(func.sum(Execution.total_cost).desc())
    )

    result = await db.execute(stmt)
    rows = result.all()

    # Calculate total cost for percentages
    total_cost = sum(float(r.cost) for r in rows) if rows else 0.0

    items: list[WorkflowBreakdownItem] = []
    for row in rows:
        cost = float(row.cost)
        pct = round((cost / total_cost) * 100, 1) if total_cost > 0 else 0.0
        items.append(
            WorkflowBreakdownItem(
                workflow_id=str(row.workflow_id),
                workflow_name=row.workflow_name,
                runs=row.runs,
                cost=round(cost, 4),
                avg_duration_sec=None,  # computed below if data exists
                cost_percentage=pct,
            )
        )

    # Compute average duration per workflow. Duration is derived in Python (for
    # cross-DB timestamp-diff compatibility), but all rows are fetched in ONE
    # query instead of one-per-workflow (avoids the N+1).
    if items:
        workflow_uuids = [uuid.UUID(item.workflow_id) for item in items]
        dur_stmt = (
            select(
                Execution.workflow_id,
                Execution.started_at,
                Execution.completed_at,
            )
            .where(
                and_(
                    Execution.tenant_id == tenant_id,
                    Execution.workflow_id.in_(workflow_uuids),
                    Execution.created_at >= period_start,
                    Execution.started_at.isnot(None),
                    Execution.completed_at.isnot(None),
                )
            )
        )
        dur_result = await db.execute(dur_stmt)
        durations_by_workflow: dict[str, list[float]] = {}
        for dr in dur_result.all():
            if dr.started_at and dr.completed_at:
                delta = (dr.completed_at - dr.started_at).total_seconds()
                durations_by_workflow.setdefault(str(dr.workflow_id), []).append(delta)
        for item in items:
            durations = durations_by_workflow.get(item.workflow_id)
            if durations:
                item.avg_duration_sec = round(sum(durations) / len(durations), 2)

    _set_cached(cache_key, items)
    return items


# ---------------------------------------------------------------------------
# Dispatch Health
# ---------------------------------------------------------------------------

def _is_webhook_execution(input_data: dict | None) -> bool:
    return (input_data or {}).get("trigger", {}).get("type") == "webhook"


def _get_rate_limit_config(config: dict | None) -> tuple[int, int] | None:
    rate_limit = (config or {}).get("rate_limit")
    if not isinstance(rate_limit, dict) or rate_limit.get("enabled") is not True:
        return None

    try:
        max_events = int(rate_limit.get("max_events"))
        window_seconds = int(rate_limit.get("window_seconds"))
    except (TypeError, ValueError):
        return None

    if max_events < 1 or window_seconds < 1:
        return None

    return max_events, window_seconds


def _dispatch_alerts(
    paused_workflows: int,
    throttled_triggers: int,
    deferred_retries: int,
    dead_lettered_executions: int,
) -> list[DispatchHealthAlert]:
    alerts: list[DispatchHealthAlert] = []
    if paused_workflows:
        alerts.append(
            DispatchHealthAlert(
                code="dispatch_paused",
                severity="warning",
                title="Workflow dispatch is paused",
                message=f"{paused_workflows} workflow dispatch queue is paused.",
                count=paused_workflows,
            )
        )
    if throttled_triggers:
        alerts.append(
            DispatchHealthAlert(
                code="trigger_throttled",
                severity="warning",
                title="Webhook triggers are throttled",
                message=f"{throttled_triggers} webhook trigger rate-limit window is exhausted.",
                count=throttled_triggers,
            )
        )
    if deferred_retries:
        alerts.append(
            DispatchHealthAlert(
                code="deferred_retries",
                severity="info",
                title="Retries are scheduled",
                message=f"{deferred_retries} webhook dispatch retry is waiting for its next attempt.",
                count=deferred_retries,
            )
        )
    if dead_lettered_executions:
        alerts.append(
            DispatchHealthAlert(
                code="dead_lettered",
                severity="critical",
                title="Dead-letter queue needs review",
                message=f"{dead_lettered_executions} webhook dispatch is dead-lettered.",
                count=dead_lettered_executions,
            )
        )
    return alerts


async def _count_throttled_triggers(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    now: datetime,
) -> int:
    trigger_result = await db.execute(
        select(WorkflowTrigger).where(
            WorkflowTrigger.tenant_id == tenant_id,
            WorkflowTrigger.trigger_type == "webhook",
            WorkflowTrigger.is_active == True,  # noqa: E712
        )
    )

    throttled = 0
    for trigger in trigger_result.scalars().all():
        rate_limit = _get_rate_limit_config(trigger.config)
        if rate_limit is None:
            continue

        max_events, window_seconds = rate_limit
        cutoff = now - timedelta(seconds=window_seconds)
        event_count = await db.scalar(
            select(func.count(WebhookEvent.id)).where(
                WebhookEvent.tenant_id == tenant_id,
                WebhookEvent.trigger_id == trigger.id,
                WebhookEvent.created_at >= cutoff,
            )
        )
        if int(event_count or 0) >= max_events:
            throttled += 1

    return throttled


async def get_dispatch_health(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    window_hours: int = 24,
) -> DispatchHealthResponse:
    """
    Aggregate operator-facing health for durable webhook dispatch.
    The response intentionally exposes only counts and alert summaries.
    """
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=window_hours)

    paused_workflows = await db.scalar(
        select(func.count(Workflow.id)).where(
            Workflow.tenant_id == tenant_id,
            Workflow.is_active == True,  # noqa: E712
            Workflow.dispatch_paused == True,  # noqa: E712
        )
    )

    execution_result = await db.execute(
        select(Execution.status, Execution.input_data).where(
            and_(
                Execution.tenant_id == tenant_id,
                Execution.created_at >= window_start,
            )
        )
    )

    pending_dispatches = 0
    deferred_retries = 0
    dead_lettered_executions = 0
    manual_retries = 0

    for status_value, input_data in execution_result.all():
        if not _is_webhook_execution(input_data):
            continue

        dispatch = (input_data or {}).get("dispatch") or {}
        if status_value == "pending":
            pending_dispatches += 1
            if dispatch.get("next_attempt_at"):
                deferred_retries += 1
        if dispatch.get("dead_lettered") is True:
            dead_lettered_executions += 1
        if dispatch.get("manual_retry") is True:
            manual_retries += 1

    throttled_triggers = await _count_throttled_triggers(db, tenant_id, now)

    return DispatchHealthResponse(
        paused_workflows=int(paused_workflows or 0),
        throttled_triggers=throttled_triggers,
        pending_dispatches=pending_dispatches,
        deferred_retries=deferred_retries,
        dead_lettered_executions=dead_lettered_executions,
        manual_retries=manual_retries,
        alerts=_dispatch_alerts(
            paused_workflows=int(paused_workflows or 0),
            throttled_triggers=throttled_triggers,
            deferred_retries=deferred_retries,
            dead_lettered_executions=dead_lettered_executions,
        ),
    )


# ---------------------------------------------------------------------------
# Dispatch Alert Policy
# ---------------------------------------------------------------------------

def _default_dispatch_alert_policy() -> DispatchAlertPolicy:
    return DispatchAlertPolicy()


def _normalize_dispatch_alert_policy(raw_policy: dict | None) -> DispatchAlertPolicy:
    if not raw_policy:
        return _default_dispatch_alert_policy()

    defaults = _default_dispatch_alert_policy().model_dump(mode="json")
    return DispatchAlertPolicy.model_validate({**defaults, **raw_policy})


def _default_dispatch_automation_worker_config() -> DispatchAutomationWorkerConfig:
    return DispatchAutomationWorkerConfig()


def _normalize_dispatch_automation_worker_config(
    raw_config: dict | None,
) -> DispatchAutomationWorkerConfig:
    if not raw_config:
        return _default_dispatch_automation_worker_config()

    defaults = _default_dispatch_automation_worker_config().model_dump(mode="json")
    return DispatchAutomationWorkerConfig.model_validate({**defaults, **raw_config})


async def _get_tenant(db: AsyncSession, tenant_id: uuid.UUID) -> Tenant:
    tenant = await db.get(Tenant, tenant_id)
    if tenant is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant not found",
        )
    return tenant


async def get_dispatch_alert_policy(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> DispatchAlertPolicy:
    tenant = await _get_tenant(db, tenant_id)
    return _normalize_dispatch_alert_policy(tenant.dispatch_alert_policy)


async def update_dispatch_alert_policy(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    policy: DispatchAlertPolicy,
) -> DispatchAlertPolicy:
    tenant = await _get_tenant(db, tenant_id)
    tenant.dispatch_alert_policy = policy.model_dump(mode="json")
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return _normalize_dispatch_alert_policy(tenant.dispatch_alert_policy)


async def get_dispatch_automation_worker_config(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> DispatchAutomationWorkerConfig:
    tenant = await _get_tenant(db, tenant_id)
    return _normalize_dispatch_automation_worker_config(
        tenant.dispatch_automation_worker_config
    )


async def update_dispatch_automation_worker_config(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    config: DispatchAutomationWorkerConfig,
) -> DispatchAutomationWorkerConfig:
    tenant = await _get_tenant(db, tenant_id)
    tenant.dispatch_automation_worker_config = config.model_dump(mode="json")
    db.add(tenant)
    await db.commit()
    await db.refresh(tenant)
    return _normalize_dispatch_automation_worker_config(
        tenant.dispatch_automation_worker_config
    )


async def record_dispatch_automation_worker_run(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    trigger_type: str,
    run_limit: int,
    claimed: int,
    executed: int,
    blocked: int,
    failed: int,
    triggered_by: uuid.UUID | None = None,
    run_status: str = "completed",
    error_message: str | None = None,
) -> DispatchAutomationWorkerRun:
    run = DispatchAutomationWorkerRun(
        tenant_id=tenant_id,
        triggered_by=triggered_by,
        trigger_type=trigger_type,
        status=run_status,
        limit=run_limit,
        claimed=claimed,
        executed=executed,
        blocked=blocked,
        failed=failed,
        error_message=sanitize_error(error_message) if error_message else None,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def list_dispatch_automation_worker_runs(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 20,
) -> DispatchAutomationWorkerRunListResponse:
    result = await db.execute(
        select(DispatchAutomationWorkerRun)
        .where(DispatchAutomationWorkerRun.tenant_id == tenant_id)
        .order_by(DispatchAutomationWorkerRun.created_at.desc())
        .limit(limit)
    )
    return DispatchAutomationWorkerRunListResponse(
        items=[
            DispatchAutomationWorkerRunItem.model_validate(run)
            for run in result.scalars().all()
        ]
    )


def _sanitize_worker_run_item(
    run: DispatchAutomationWorkerRun,
) -> DispatchAutomationWorkerRunItem:
    return DispatchAutomationWorkerRunItem(
        id=run.id,
        trigger_type=run.trigger_type,
        status=run.status,
        limit=run.limit,
        claimed=run.claimed,
        executed=run.executed,
        blocked=run.blocked,
        failed=run.failed,
        error_message=sanitize_error(run.error_message) if run.error_message else None,
        created_at=run.created_at,
    )


async def _latest_scheduled_automation_worker_run(
    db: AsyncSession,
    tenant_id: uuid.UUID,
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


def _automation_worker_due_state(
    *,
    config: DispatchAutomationWorkerConfig,
    latest_run: DispatchAutomationWorkerRun | None,
    now: datetime,
) -> tuple[bool, str | None, datetime | None, datetime | None]:
    if not config.enabled:
        return False, "tenant_disabled", None, None
    if latest_run is None or latest_run.created_at is None:
        return True, None, None, None

    latest_created_at = _ensure_utc(latest_run.created_at)
    if latest_run.status == "failed":
        backoff_until = latest_created_at + timedelta(
            minutes=max(
                config.interval_minutes,
                DISPATCH_AUTOMATION_FAILED_RUN_BACKOFF_MINUTES,
            )
        )
        if now < backoff_until:
            return False, "backoff", backoff_until, backoff_until
        return True, None, None, backoff_until

    next_run_at = latest_created_at + timedelta(minutes=config.interval_minutes)
    if now < next_run_at:
        return False, "interval", next_run_at, None
    return True, None, None, None


async def get_dispatch_automation_worker_diagnostics(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    *,
    scheduler_enabled: bool,
    scheduler_interval_seconds: float,
    scheduler_tenant_limit: int,
    now: datetime | None = None,
) -> DispatchAutomationWorkerDiagnosticsResponse:
    current_time = _ensure_utc(now or datetime.now(timezone.utc))
    config = await get_dispatch_automation_worker_config(db, tenant_id)
    approved_plan_count = await db.scalar(
        select(func.count(DispatchAutomationPlan.id)).where(
            DispatchAutomationPlan.tenant_id == tenant_id,
            DispatchAutomationPlan.status == "approved",
        )
    )
    latest_run = await _latest_scheduled_automation_worker_run(db, tenant_id)
    tenant_due_now, skip_reason, next_run_at, backoff_until = _automation_worker_due_state(
        config=config,
        latest_run=latest_run,
        now=current_time,
    )

    return DispatchAutomationWorkerDiagnosticsResponse(
        generated_at=current_time,
        scheduler_enabled=scheduler_enabled,
        scheduler_interval_seconds=scheduler_interval_seconds,
        scheduler_tenant_limit=scheduler_tenant_limit,
        tenant_config=config,
        approved_plan_count=int(approved_plan_count or 0),
        latest_scheduled_run=(
            _sanitize_worker_run_item(latest_run) if latest_run is not None else None
        ),
        tenant_due_now=tenant_due_now,
        tenant_skip_reason=skip_reason,
        next_run_at=next_run_at,
        backoff_until=backoff_until,
    )


async def preview_dispatch_alert_policy(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    window_hours: int = 24,
) -> DispatchAlertPolicyPreview:
    policy = await get_dispatch_alert_policy(db, tenant_id)
    health = await get_dispatch_health(
        db=db,
        tenant_id=tenant_id,
        window_hours=window_hours,
    )
    matched_alerts = [
        alert
        for alert in health.alerts
        if alert.severity in policy.severities and alert.code in policy.alert_codes
    ]

    alert_codes = [alert.code for alert in matched_alerts]
    routes: list[DispatchAlertPolicyPreviewRoute] = []
    if policy.enabled and alert_codes:
        for channel in policy.channels:
            if not channel.enabled:
                continue
            routes.append(
                DispatchAlertPolicyPreviewRoute(
                    channel_type=channel.type,
                    target=channel.target,
                    alert_codes=alert_codes,
                )
            )

    return DispatchAlertPolicyPreview(
        dry_run=True,
        policy_enabled=policy.enabled,
        alerts=matched_alerts,
        routes=routes,
    )


# ---------------------------------------------------------------------------
# Dispatch Alert Delivery
# ---------------------------------------------------------------------------

def _webhook_target_preview(url: str) -> str:
    parsed = urlparse(url)
    path = parsed.path or ""
    return f"{parsed.scheme}://{parsed.netloc}{path}"


def _build_channel_config_preview(channel_type: str, config: dict) -> dict:
    if channel_type == "webhook":
        return {
            "url": _webhook_target_preview(str(config.get("url") or "")),
            "headers": redact_secret_values(config.get("headers") or {}),
        }
    return redact_secret_values(config)


def _validate_channel_config(channel_type: str, config: dict) -> None:
    if channel_type != "webhook":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Slice 7 supports only webhook dispatch alert channels.",
        )
    url = config.get("url")
    if not isinstance(url, str) or not url:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Webhook alert channel requires url.",
        )
    try:
        from app.services.connector_runtime_service import (
            ConnectorRuntimeError,
            assert_public_http_url,
        )

        assert_public_http_url(url)
    except ConnectorRuntimeError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=exc.sanitized_error,
        ) from exc
    headers = config.get("headers")
    if headers is not None and not isinstance(headers, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Webhook alert channel headers must be an object.",
        )


async def create_dispatch_alert_channel(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    data: DispatchAlertChannelCredentialCreate,
) -> DispatchAlertChannelCredential:
    _validate_channel_config(data.channel_type, data.config)
    channel = DispatchAlertChannelCredential(
        tenant_id=tenant_id,
        name=data.name,
        channel_type=data.channel_type,
        encrypted_config=encrypt_config(data.config),
        config_preview=_build_channel_config_preview(data.channel_type, data.config),
        created_by=user_id,
    )
    db.add(channel)
    await db.commit()
    await db.refresh(channel)
    return channel


async def list_dispatch_alert_channels(
    db: AsyncSession,
    tenant_id: uuid.UUID,
) -> DispatchAlertChannelCredentialListResponse:
    result = await db.execute(
        select(DispatchAlertChannelCredential)
        .where(
            DispatchAlertChannelCredential.tenant_id == tenant_id,
            DispatchAlertChannelCredential.is_active == True,  # noqa: E712
        )
        .order_by(DispatchAlertChannelCredential.created_at.desc())
    )
    return DispatchAlertChannelCredentialListResponse(
        items=[
            DispatchAlertChannelCredentialResponse.model_validate(channel)
            for channel in result.scalars().all()
        ]
    )


async def _get_dispatch_alert_channel(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    channel_id: uuid.UUID,
) -> DispatchAlertChannelCredential | None:
    result = await db.execute(
        select(DispatchAlertChannelCredential).where(
            DispatchAlertChannelCredential.id == channel_id,
            DispatchAlertChannelCredential.tenant_id == tenant_id,
            DispatchAlertChannelCredential.is_active == True,  # noqa: E712
        )
    )
    return result.scalar_one_or_none()


async def _alert_is_in_cooldown(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    channel_id: uuid.UUID,
    alert_code: str,
    cooldown_minutes: int,
    now: datetime,
) -> bool:
    cutoff = now - timedelta(minutes=cooldown_minutes)
    recent_count = await db.scalar(
        select(func.count(DispatchAlertDelivery.id)).where(
            DispatchAlertDelivery.tenant_id == tenant_id,
            DispatchAlertDelivery.channel_id == channel_id,
            DispatchAlertDelivery.alert_code == alert_code,
            DispatchAlertDelivery.created_at >= cutoff,
        )
    )
    return int(recent_count or 0) > 0


async def _deliver_webhook_notification(
    config: dict,
    alerts: list[DispatchHealthAlert],
) -> SimpleNamespace:
    from app.engine.tools.safe_http import pinned_http_request

    url = str(config.get("url") or "")
    headers = dict(config.get("headers") or {})
    timeout = float(config.get("timeout_seconds") or 10)
    payload = {
        "event": "dispatch_alert",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "alerts": [alert.model_dump(mode="json") for alert in alerts],
    }
    try:
        # IP-pinned delivery: re-validates and connects to the resolved public
        # address, closing the DNS-rebinding window between channel validation and
        # delivery time. http is permitted to preserve existing channel behavior.
        response = await pinned_http_request(
            "POST",
            url,
            headers=headers,
            json_body=payload,
            timeout=timeout,
            allow_http=True,
        )
        status_code = int(response["status_code"])
        if status_code >= 400:
            return SimpleNamespace(
                status="failed",
                status_code=status_code,
                error_message=sanitize_error(
                    str(response.get("body_text") or "")[:500] or "Webhook delivery failed."
                ),
            )
        return SimpleNamespace(
            status="delivered",
            status_code=status_code,
            error_message=None,
        )
    except Exception as exc:
        return SimpleNamespace(
            status="failed",
            status_code=None,
            error_message=sanitize_error(str(exc)),
        )


async def deliver_dispatch_alerts(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    window_hours: int = 24,
    enforce_cooldown: bool = True,
) -> DispatchAlertDeliveryResponse:
    preview = await preview_dispatch_alert_policy(db, tenant_id, window_hours)
    if not preview.policy_enabled or not preview.alerts:
        return DispatchAlertDeliveryResponse(attempted=0, delivered=0, failed=0, skipped=0, items=[])

    policy = await get_dispatch_alert_policy(db, tenant_id)
    now = datetime.now(timezone.utc)
    items: list[DispatchAlertDelivery] = []
    attempted = 0
    delivered = 0
    failed = 0
    skipped = 0

    for route in policy.channels:
        if not route.enabled:
            continue
        if route.credential_id is None:
            skipped += len(preview.alerts)
            continue
        channel = await _get_dispatch_alert_channel(db, tenant_id, route.credential_id)
        if channel is None:
            skipped += len(preview.alerts)
            continue

        alerts_to_deliver: list[DispatchHealthAlert] = []
        for alert in preview.alerts:
            if enforce_cooldown and await _alert_is_in_cooldown(
                db=db,
                tenant_id=tenant_id,
                channel_id=channel.id,
                alert_code=alert.code,
                cooldown_minutes=policy.cooldown_minutes,
                now=now,
            ):
                skipped += 1
                continue
            alerts_to_deliver.append(alert)
        if not alerts_to_deliver:
            continue

        config = decrypt_config(channel.encrypted_config)
        if channel.channel_type == "webhook":
            result = await _deliver_webhook_notification(config, alerts_to_deliver)
        else:
            result = SimpleNamespace(
                status="failed",
                status_code=None,
                error_message="Unsupported dispatch alert channel.",
            )

        for alert in alerts_to_deliver:
            attempted += 1
            if result.status == "delivered":
                delivered += 1
            else:
                failed += 1
            delivery = DispatchAlertDelivery(
                tenant_id=tenant_id,
                channel_id=channel.id,
                alert_code=alert.code,
                channel_type=channel.channel_type,
                target_preview=str(channel.config_preview.get("url") or route.target),
                status=result.status,
                status_code=result.status_code,
                error_message=sanitize_error(result.error_message) if result.error_message else None,
            )
            db.add(delivery)
            items.append(delivery)

    await db.commit()
    for item in items:
        await db.refresh(item)

    return DispatchAlertDeliveryResponse(
        attempted=attempted,
        delivered=delivered,
        failed=failed,
        skipped=skipped,
        items=items,
    )


async def list_dispatch_alert_deliveries(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 20,
) -> DispatchAlertDeliveryListResponse:
    result = await db.execute(
        select(DispatchAlertDelivery)
        .where(DispatchAlertDelivery.tenant_id == tenant_id)
        .order_by(DispatchAlertDelivery.created_at.desc())
        .limit(limit)
    )
    return DispatchAlertDeliveryListResponse(items=list(result.scalars().all()))


# ---------------------------------------------------------------------------
# Dispatch Runbook
# ---------------------------------------------------------------------------

def _runbook_severity(alerts: list[DispatchHealthAlert]) -> str:
    severities = {alert.severity for alert in alerts}
    if "critical" in severities:
        return "critical"
    if "warning" in severities:
        return "warning"
    return "info"


def _incident_key_for_alerts(alerts: list[DispatchHealthAlert]) -> str | None:
    if not alerts:
        return None
    return "dispatch:" + ",".join(sorted({alert.code for alert in alerts}))


async def _get_current_runbook_context(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    window_hours: int,
) -> tuple[DispatchHealthResponse, DispatchAlertPolicy, list[DispatchHealthAlert]]:
    health = await get_dispatch_health(db=db, tenant_id=tenant_id, window_hours=window_hours)
    policy = await get_dispatch_alert_policy(db=db, tenant_id=tenant_id)
    matched_alerts = [
        alert
        for alert in health.alerts
        if alert.severity in policy.severities and alert.code in policy.alert_codes
    ]
    return health, policy, matched_alerts


def _runbook_actions(
    alerts: list[DispatchHealthAlert],
    policy: DispatchAlertPolicy,
) -> list[DispatchRunbookAction]:
    if not alerts:
        return [
            DispatchRunbookAction(
                title="Continue monitoring dispatch health",
                detail="No active dispatch incident needs handoff.",
                priority="info",
            )
        ]

    actions: list[DispatchRunbookAction] = []
    alert_codes = {alert.code for alert in alerts}
    if "dead_lettered" in alert_codes:
        actions.append(
            DispatchRunbookAction(
                title="Dead-letter queue needs review",
                detail="Inspect failed webhook dispatches, fix the root cause, then retry only eligible dead-lettered executions.",
                priority="critical",
            )
        )
    if "dispatch_paused" in alert_codes:
        actions.append(
            DispatchRunbookAction(
                title="Confirm paused workflow ownership",
                detail="Identify why webhook dispatch is paused and resume only after downstream dependencies are healthy.",
                priority="warning",
            )
        )
    if "trigger_throttled" in alert_codes:
        actions.append(
            DispatchRunbookAction(
                title="Review webhook trigger rate limits",
                detail="Check whether incoming volume is expected before raising trigger limits or extending the cooldown window.",
                priority="warning",
            )
        )
    if "deferred_retries" in alert_codes:
        actions.append(
            DispatchRunbookAction(
                title="Watch deferred retry backlog",
                detail="Confirm retry scheduling is draining and investigate if deferred retries keep growing.",
                priority="info",
            )
        )
    if not policy.enabled:
        actions.append(
            DispatchRunbookAction(
                title="Enable dispatch alert routing",
                detail="Alert routing is disabled; enable the policy before relying on automated incident notifications.",
                priority="warning",
            )
        )
    return actions


def _sanitize_delivery_item(delivery: DispatchAlertDelivery) -> DispatchAlertDeliveryItem:
    return DispatchAlertDeliveryItem(
        id=delivery.id,
        alert_code=delivery.alert_code,
        channel_type=delivery.channel_type,
        target_preview=sanitize_error(delivery.target_preview),
        status=delivery.status,
        status_code=delivery.status_code,
        error_message=sanitize_error(delivery.error_message) if delivery.error_message else None,
        created_at=delivery.created_at,
    )


async def _get_open_incident_acknowledgement(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    incident_key: str | None,
) -> DispatchIncidentAcknowledgement | None:
    if incident_key is None:
        return None
    result = await db.execute(
        select(DispatchIncidentAcknowledgement).where(
            DispatchIncidentAcknowledgement.tenant_id == tenant_id,
            DispatchIncidentAcknowledgement.incident_key == incident_key,
            DispatchIncidentAcknowledgement.status == "acknowledged",
        )
    )
    return result.scalar_one_or_none()


async def list_dispatch_incident_history(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 20,
) -> DispatchIncidentHistoryResponse:
    result = await db.execute(
        select(DispatchIncidentAcknowledgement)
        .where(DispatchIncidentAcknowledgement.tenant_id == tenant_id)
        .order_by(DispatchIncidentAcknowledgement.updated_at.desc())
        .limit(limit)
    )
    return DispatchIncidentHistoryResponse(
        items=[
            DispatchIncidentAcknowledgementResponse.model_validate(row)
            for row in result.scalars().all()
        ]
    )


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _duration_minutes(start: datetime, end: datetime) -> float:
    start_utc = _ensure_utc(start)
    end_utc = _ensure_utc(end)
    return max((end_utc - start_utc).total_seconds() / 60, 0.0)


def _incident_resolution_minutes(
    row: DispatchIncidentAcknowledgement,
) -> float | None:
    if row.resolved_at is None:
        return None
    return _duration_minutes(row.created_at, row.resolved_at)


def _incident_sla_breached(
    row: DispatchIncidentAcknowledgement,
    now: datetime,
    sla_minutes: int,
) -> bool:
    if row.resolved_at is not None:
        duration = _duration_minutes(row.created_at, row.resolved_at)
    else:
        duration = _duration_minutes(row.created_at, now)
    return duration > sla_minutes


def _avg_minutes(values: list[float]) -> float | None:
    if not values:
        return None
    return round(sum(values) / len(values), 1)


async def get_dispatch_incident_analytics(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    days: int = 30,
    sla_minutes: int = 60,
) -> DispatchIncidentAnalyticsResponse:
    now = datetime.now(timezone.utc)
    start_day = (now - timedelta(days=days - 1)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    trend_map: dict[str, dict[str, int]] = {}
    current_day = start_day
    for _ in range(days):
        day = current_day.strftime("%Y-%m-%d")
        trend_map[day] = {
            "acknowledged": 0,
            "resolved": 0,
            "open": 0,
            "sla_breaches": 0,
        }
        current_day += timedelta(days=1)

    result = await db.execute(
        select(DispatchIncidentAcknowledgement)
        .where(
            DispatchIncidentAcknowledgement.tenant_id == tenant_id,
            DispatchIncidentAcknowledgement.created_at >= start_day,
        )
        .order_by(DispatchIncidentAcknowledgement.created_at.asc())
    )
    rows = list(result.scalars().all())

    total_incidents = len(rows)
    resolved_incidents = 0
    open_incidents = 0
    sla_breaches = 0
    resolution_durations: list[float] = []
    severity_stats: dict[str, dict[str, object]] = {}

    for row in rows:
        created_at = _ensure_utc(row.created_at)
        day_key = created_at.strftime("%Y-%m-%d")
        trend = trend_map.setdefault(
            day_key,
            {"acknowledged": 0, "resolved": 0, "open": 0, "sla_breaches": 0},
        )
        trend["acknowledged"] += 1

        severity = row.severity or "info"
        stats = severity_stats.setdefault(
            severity,
            {
                "total_incidents": 0,
                "resolved_incidents": 0,
                "open_incidents": 0,
                "sla_breaches": 0,
                "durations": [],
            },
        )
        stats["total_incidents"] = int(stats["total_incidents"]) + 1

        resolution_minutes = _incident_resolution_minutes(row)
        if row.status == "resolved" and resolution_minutes is not None:
            resolved_incidents += 1
            trend["resolved"] += 1
            resolution_durations.append(resolution_minutes)
            stats["resolved_incidents"] = int(stats["resolved_incidents"]) + 1
            stats["durations"].append(resolution_minutes)
        else:
            open_incidents += 1
            trend["open"] += 1
            stats["open_incidents"] = int(stats["open_incidents"]) + 1

        if _incident_sla_breached(row, now, sla_minutes):
            sla_breaches += 1
            trend["sla_breaches"] += 1
            stats["sla_breaches"] = int(stats["sla_breaches"]) + 1

    severity_order = {"critical": 0, "warning": 1, "info": 2}
    by_severity = []
    for severity, stats in sorted(
        severity_stats.items(),
        key=lambda item: (severity_order.get(item[0], 99), item[0]),
    ):
        by_severity.append(
            DispatchIncidentSeverityBreakdownItem(
                severity=severity,
                total_incidents=int(stats["total_incidents"]),
                resolved_incidents=int(stats["resolved_incidents"]),
                open_incidents=int(stats["open_incidents"]),
                sla_breaches=int(stats["sla_breaches"]),
                avg_resolution_minutes=_avg_minutes(stats["durations"]),
            )
        )

    return DispatchIncidentAnalyticsResponse(
        generated_at=now,
        window_days=days,
        sla_minutes=sla_minutes,
        total_incidents=total_incidents,
        resolved_incidents=resolved_incidents,
        open_incidents=open_incidents,
        sla_breaches=sla_breaches,
        sla_breach_rate=round((sla_breaches / total_incidents) * 100, 1)
        if total_incidents
        else 0.0,
        avg_resolution_minutes=_avg_minutes(resolution_durations),
        trends=[
            DispatchIncidentTrendItem(day=day, **values)
            for day, values in sorted(trend_map.items())
        ],
        by_severity=by_severity,
    )


def _automation_recommendation(
    *,
    code: str,
    priority: str,
    title: str,
    rationale: str,
    suggested_action: str,
    automation_type: str,
    confidence: float,
    evidence: list[str],
    blocked_by: list[str] | None = None,
) -> DispatchAutomationRecommendation:
    return DispatchAutomationRecommendation(
        code=code,
        priority=priority,
        title=title,
        rationale=rationale,
        suggested_action=suggested_action,
        automation_type=automation_type,
        confidence=confidence,
        evidence=evidence,
        blocked_by=blocked_by or [],
    )


async def get_dispatch_control_recommendations(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    window_hours: int = 24,
    sla_minutes: int = 60,
) -> DispatchControlRecommendationsResponse:
    health = await get_dispatch_health(
        db=db,
        tenant_id=tenant_id,
        window_hours=window_hours,
    )
    policy = await get_dispatch_alert_policy(db=db, tenant_id=tenant_id)
    incident_analytics = await get_dispatch_incident_analytics(
        db=db,
        tenant_id=tenant_id,
        days=30,
        sla_minutes=sla_minutes,
    )

    recommendations: list[DispatchAutomationRecommendation] = []
    if health.dead_lettered_executions:
        recommendations.append(
            _automation_recommendation(
                code="auto_retry_dead_letters",
                priority="critical",
                title="Automate eligible dead-letter retry triage",
                rationale="Dead-lettered webhook dispatches are waiting for operator review.",
                suggested_action="Create an approval-gated retry plan for eligible dead-lettered dispatches after root-cause review.",
                automation_type="approval_gated_retry",
                confidence=0.92,
                evidence=[
                    f"{health.dead_lettered_executions} dead-lettered webhook dispatch in the last {window_hours} hours"
                ],
            )
        )

    if health.paused_workflows:
        recommendations.append(
            _automation_recommendation(
                code="auto_resume_guard",
                priority="warning",
                title="Add a guarded dispatch resume workflow",
                rationale="Paused workflow dispatch can linger after downstream systems recover.",
                suggested_action="Create a resume checklist that verifies downstream health before proposing workflow dispatch resume.",
                automation_type="resume_guard",
                confidence=0.82,
                evidence=[
                    f"{health.paused_workflows} paused workflow dispatch queue in the last {window_hours} hours"
                ],
            )
        )

    if health.throttled_triggers:
        recommendations.append(
            _automation_recommendation(
                code="auto_rate_limit_tuning",
                priority="warning",
                title="Recommend webhook rate-limit tuning",
                rationale="Webhook trigger rate-limit windows are exhausted.",
                suggested_action="Generate a rate-limit tuning proposal from recent volume before operators change trigger thresholds.",
                automation_type="rate_limit_tuning",
                confidence=0.78,
                evidence=[
                    f"{health.throttled_triggers} webhook trigger rate-limit window exhausted"
                ],
            )
        )

    if health.deferred_retries:
        recommendations.append(
            _automation_recommendation(
                code="auto_retry_backlog_watch",
                priority="info",
                title="Watch deferred retry backlog",
                rationale="Deferred retries can hide a slow-draining dispatch queue.",
                suggested_action="Create a backlog watcher that escalates only when deferred retries keep growing across windows.",
                automation_type="backlog_monitor",
                confidence=0.7,
                evidence=[
                    f"{health.deferred_retries} deferred retry waiting in the last {window_hours} hours"
                ],
            )
        )

    if incident_analytics.sla_breaches:
        recommendations.append(
            _automation_recommendation(
                code="auto_sla_escalation",
                priority="critical" if incident_analytics.sla_breach_rate >= 50 else "warning",
                title="Add incident SLA escalation automation",
                rationale="Recent dispatch incidents breached the configured resolution SLA.",
                suggested_action="Create a dry-run escalation plan that pages owners only after alert routing credentials are configured.",
                automation_type="sla_escalation",
                confidence=0.87,
                evidence=[
                    f"{incident_analytics.sla_breaches} SLA breach in the last 30 days",
                    f"{incident_analytics.sla_breach_rate}% breach rate at {sla_minutes} minute SLA",
                ],
                blocked_by=[] if policy.enabled else ["No active alert routing policy"],
            )
        )

    if not policy.enabled:
        recommendations.append(
            _automation_recommendation(
                code="setup_alert_routing",
                priority="warning",
                title="Enable automated alert routing",
                rationale="Alert routing is disabled, so automated escalation has no safe delivery path.",
                suggested_action="Configure a credential-backed alert route before enabling automated incident escalation.",
                automation_type="alert_routing_setup",
                confidence=0.74,
                evidence=["Dispatch alert policy is disabled"],
                blocked_by=["No active alert routing policy"],
            )
        )

    automation_ready_count = len(
        [recommendation for recommendation in recommendations if not recommendation.blocked_by]
    )

    return DispatchControlRecommendationsResponse(
        generated_at=datetime.now(timezone.utc),
        dry_run=True,
        window_hours=window_hours,
        sla_minutes=sla_minutes,
        recommendation_count=len(recommendations),
        automation_ready_count=automation_ready_count,
        recommendations=recommendations,
    )


async def _find_current_dispatch_recommendation(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    recommendation_code: str,
    window_hours: int,
    sla_minutes: int,
) -> DispatchAutomationRecommendation | None:
    response = await get_dispatch_control_recommendations(
        db=db,
        tenant_id=tenant_id,
        window_hours=window_hours,
        sla_minutes=sla_minutes,
    )
    return next(
        (
            recommendation
            for recommendation in response.recommendations
            if recommendation.code == recommendation_code
        ),
        None,
    )


async def _get_dispatch_automation_plan(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    plan_id: uuid.UUID,
) -> DispatchAutomationPlan:
    result = await db.execute(
        select(DispatchAutomationPlan).where(
            DispatchAutomationPlan.id == plan_id,
            DispatchAutomationPlan.tenant_id == tenant_id,
        )
    )
    plan = result.scalar_one_or_none()
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dispatch automation plan not found.",
        )
    return plan


async def create_dispatch_automation_plan(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user: User,
    data: DispatchAutomationPlanCreate,
    window_hours: int = 24,
    sla_minutes: int = 60,
) -> DispatchAutomationPlan:
    recommendation = await _find_current_dispatch_recommendation(
        db=db,
        tenant_id=tenant_id,
        recommendation_code=data.recommendation_code,
        window_hours=window_hours,
        sla_minutes=sla_minutes,
    )
    if recommendation is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Recommendation is not current for this tenant.",
        )

    existing = await db.scalar(
        select(func.count(DispatchAutomationPlan.id)).where(
            DispatchAutomationPlan.tenant_id == tenant_id,
            DispatchAutomationPlan.recommendation_code == data.recommendation_code,
            DispatchAutomationPlan.status == "pending_approval",
        )
    )
    if int(existing or 0) > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A pending automation plan already exists for this recommendation.",
        )

    plan = DispatchAutomationPlan(
        tenant_id=tenant_id,
        recommendation_code=recommendation.code,
        automation_type=recommendation.automation_type,
        status="pending_approval",
        priority=recommendation.priority,
        title=recommendation.title,
        rationale=recommendation.rationale,
        suggested_action=recommendation.suggested_action,
        confidence=recommendation.confidence,
        evidence=recommendation.evidence,
        blocked_by=recommendation.blocked_by,
        requested_by=user.id,
        requested_by_email=user.email,
        requested_by_name=user.full_name,
    )
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def list_dispatch_automation_plans(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    limit: int = 20,
) -> DispatchAutomationPlanListResponse:
    result = await db.execute(
        select(DispatchAutomationPlan)
        .where(DispatchAutomationPlan.tenant_id == tenant_id)
        .order_by(DispatchAutomationPlan.created_at.desc())
        .limit(limit)
    )
    return DispatchAutomationPlanListResponse(
        items=[
            DispatchAutomationPlanResponse.model_validate(plan)
            for plan in result.scalars().all()
        ]
    )


async def approve_dispatch_automation_plan(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user: User,
    plan_id: uuid.UUID,
) -> DispatchAutomationPlan:
    plan = await _get_dispatch_automation_plan(db=db, tenant_id=tenant_id, plan_id=plan_id)
    if plan.status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending automation plans can be approved.",
        )
    plan.status = "approved"
    plan.approved_by = user.id
    plan.approved_by_email = user.email
    plan.approved_by_name = user.full_name
    plan.approved_at = datetime.now(timezone.utc)
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def reject_dispatch_automation_plan(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user: User,
    plan_id: uuid.UUID,
    data: DispatchAutomationPlanReject,
) -> DispatchAutomationPlan:
    plan = await _get_dispatch_automation_plan(db=db, tenant_id=tenant_id, plan_id=plan_id)
    if plan.status != "pending_approval":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only pending automation plans can be rejected.",
        )
    plan.status = "rejected"
    plan.rejected_by = user.id
    plan.rejected_by_email = user.email
    plan.rejected_by_name = user.full_name
    plan.rejection_note = sanitize_error(data.rejection_note) if data.rejection_note else None
    plan.rejected_at = datetime.now(timezone.utc)
    db.add(plan)
    await db.commit()
    await db.refresh(plan)
    return plan


async def get_dispatch_runbook(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    window_hours: int = 24,
    delivery_limit: int = 10,
) -> DispatchRunbookResponse:
    health, policy, matched_alerts = await _get_current_runbook_context(
        db=db,
        tenant_id=tenant_id,
        window_hours=window_hours,
    )
    delivery_rows = (
        await db.execute(
            select(DispatchAlertDelivery)
            .where(DispatchAlertDelivery.tenant_id == tenant_id)
            .order_by(DispatchAlertDelivery.created_at.desc())
            .limit(delivery_limit)
        )
    ).scalars().all()
    severity = _runbook_severity(matched_alerts)
    acknowledgement = await _get_open_incident_acknowledgement(
        db=db,
        tenant_id=tenant_id,
        incident_key=_incident_key_for_alerts(matched_alerts),
    )
    history = await list_dispatch_incident_history(db=db, tenant_id=tenant_id, limit=5)

    return DispatchRunbookResponse(
        tenant_id=tenant_id,
        generated_at=datetime.now(timezone.utc),
        window_hours=window_hours,
        severity=severity,
        summary=(
            "Dispatch incident handoff required"
            if matched_alerts
            else "No active dispatch incident"
        ),
        health=health,
        policy=DispatchRunbookPolicy(
            enabled=policy.enabled,
            configured_channels=len([channel for channel in policy.channels if channel.enabled]),
            cooldown_minutes=policy.cooldown_minutes,
        ),
        alerts=matched_alerts,
        recent_deliveries=[_sanitize_delivery_item(delivery) for delivery in delivery_rows],
        recommended_actions=_runbook_actions(matched_alerts, policy),
        acknowledgement=(
            DispatchIncidentAcknowledgementResponse.model_validate(acknowledgement)
            if acknowledgement
            else None
        ),
        incident_history=history.items,
    )


async def get_dispatch_incident_acknowledgement(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    window_hours: int = 24,
) -> DispatchIncidentAcknowledgementState:
    _health, _policy, matched_alerts = await _get_current_runbook_context(
        db=db,
        tenant_id=tenant_id,
        window_hours=window_hours,
    )
    acknowledgement = await _get_open_incident_acknowledgement(
        db=db,
        tenant_id=tenant_id,
        incident_key=_incident_key_for_alerts(matched_alerts),
    )
    return DispatchIncidentAcknowledgementState(
        acknowledgement=(
            DispatchIncidentAcknowledgementResponse.model_validate(acknowledgement)
            if acknowledgement
            else None
        )
    )


async def acknowledge_dispatch_incident(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user: User,
    data: DispatchIncidentAcknowledgementCreate,
    window_hours: int = 24,
) -> DispatchIncidentAcknowledgement:
    _health, _policy, matched_alerts = await _get_current_runbook_context(
        db=db,
        tenant_id=tenant_id,
        window_hours=window_hours,
    )
    incident_key = _incident_key_for_alerts(matched_alerts)
    if incident_key is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No active dispatch incident to acknowledge.",
        )

    acknowledgement = await _get_open_incident_acknowledgement(
        db=db,
        tenant_id=tenant_id,
        incident_key=incident_key,
    )
    if acknowledgement is None:
        acknowledgement = DispatchIncidentAcknowledgement(
            tenant_id=tenant_id,
            incident_key=incident_key,
        )

    acknowledgement.status = "acknowledged"
    acknowledgement.severity = _runbook_severity(matched_alerts)
    acknowledgement.summary = "Dispatch incident handoff required"
    acknowledgement.alert_codes = sorted({alert.code for alert in matched_alerts})
    acknowledgement.acknowledged_by = user.id
    acknowledgement.acknowledged_by_email = user.email
    acknowledgement.acknowledged_by_name = user.full_name
    acknowledgement.note = sanitize_error(data.note) if data.note else None
    db.add(acknowledgement)
    await db.commit()
    await db.refresh(acknowledgement)
    return acknowledgement


async def resolve_dispatch_incident(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    user: User,
    data: DispatchIncidentResolutionCreate,
    window_hours: int = 24,
) -> DispatchIncidentAcknowledgement:
    _health, _policy, matched_alerts = await _get_current_runbook_context(
        db=db,
        tenant_id=tenant_id,
        window_hours=window_hours,
    )
    acknowledgement = await _get_open_incident_acknowledgement(
        db=db,
        tenant_id=tenant_id,
        incident_key=_incident_key_for_alerts(matched_alerts),
    )
    if acknowledgement is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="No acknowledged dispatch incident to resolve.",
        )

    acknowledgement.status = "resolved"
    acknowledgement.resolved_by = user.id
    acknowledgement.resolved_by_email = user.email
    acknowledgement.resolved_by_name = user.full_name
    acknowledgement.resolution_note = (
        sanitize_error(data.resolution_note) if data.resolution_note else None
    )
    acknowledgement.resolved_at = datetime.now(timezone.utc)
    db.add(acknowledgement)
    await db.commit()
    await db.refresh(acknowledgement)
    return acknowledgement


def render_dispatch_runbook_markdown(runbook: DispatchRunbookResponse) -> str:
    lines = [
        "# Dispatch Incident Runbook",
        "",
        f"- Generated at: {runbook.generated_at.isoformat()}",
        f"- Severity: {runbook.severity}",
        f"- Summary: {sanitize_error(runbook.summary)}",
        f"- Window: {runbook.window_hours} hours",
        "",
        "## Health",
        "",
        f"- Paused workflows: {runbook.health.paused_workflows}",
        f"- Throttled triggers: {runbook.health.throttled_triggers}",
        f"- Pending dispatches: {runbook.health.pending_dispatches}",
        f"- Deferred retries: {runbook.health.deferred_retries}",
        f"- Dead-lettered executions: {runbook.health.dead_lettered_executions}",
        f"- Manual retries: {runbook.health.manual_retries}",
        "",
        "## Alerts",
        "",
    ]

    if runbook.alerts:
        for alert in runbook.alerts:
            lines.append(
                f"- [{alert.severity}] {sanitize_error(alert.title)} ({alert.code}): {sanitize_error(alert.message)}"
            )
    else:
        lines.append("- No active dispatch alerts.")

    lines.extend(["", "## Recommended Actions", ""])
    for action in runbook.recommended_actions:
        lines.append(
            f"- [{action.priority}] {sanitize_error(action.title)}: {sanitize_error(action.detail)}"
        )

    lines.extend(["", "## Ownership", ""])
    if runbook.acknowledgement:
        owner = sanitize_error(runbook.acknowledgement.acknowledged_by_email)
        note = sanitize_error(runbook.acknowledgement.note or "")
        lines.append(f"- Acknowledged by: {owner}")
        if note:
            lines.append(f"- Note: {note}")
    else:
        lines.append("- Not acknowledged.")

    lines.extend(["", "## Recent Delivery Audit", ""])
    if runbook.recent_deliveries:
        for delivery in runbook.recent_deliveries:
            status_code = f" HTTP {delivery.status_code}" if delivery.status_code else ""
            lines.append(
                f"- {delivery.alert_code} -> {delivery.status}{status_code} ({sanitize_error(delivery.target_preview)})"
            )
    else:
        lines.append("- No recent delivery attempts.")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

async def get_export_data(
    db: AsyncSession,
    tenant_id: uuid.UUID,
    format: str = "csv",
    from_date: datetime | None = None,
    to_date: datetime | None = None,
    limit: int = 50000,
) -> tuple[list[ExportRow], str]:
    """
    Export execution data as a list of ExportRow objects.
    Returns (rows, format_str).
    Max 50 000 rows.
    """
    conditions = [Execution.tenant_id == tenant_id]
    if from_date:
        conditions.append(Execution.created_at >= from_date)
    if to_date:
        conditions.append(Execution.created_at <= to_date)

    stmt = (
        select(
            Execution.id.label("execution_id"),
            Workflow.name.label("workflow_name"),
            Execution.status,
            Execution.total_tokens.label("tokens"),
            Execution.total_cost.label("cost"),
            Execution.started_at,
            Execution.completed_at,
        )
        .join(Workflow, Execution.workflow_id == Workflow.id)
        .where(and_(*conditions))
        .order_by(Execution.created_at.desc())
        .limit(limit)
    )

    result = await db.execute(stmt)
    rows = result.all()

    export_rows = [
        ExportRow(
            execution_id=str(r.execution_id),
            workflow_name=r.workflow_name,
            status=r.status,
            tokens=r.tokens or 0,
            cost=round(float(r.cost or 0.0), 4),
            started_at=r.started_at.isoformat() if r.started_at else None,
            completed_at=r.completed_at.isoformat() if r.completed_at else None,
        )
        for r in rows
    ]

    return export_rows, format


def export_rows_to_csv(rows: list[ExportRow]) -> str:
    """Convert ExportRow list to CSV string."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        ["execution_id", "workflow_name", "status", "tokens", "cost", "started_at", "completed_at"]
    )
    for r in rows:
        writer.writerow(
            [r.execution_id, r.workflow_name, r.status, r.tokens, r.cost, r.started_at, r.completed_at]
        )
    return output.getvalue()


def export_rows_to_json(rows: list[ExportRow]) -> list[dict]:
    """Convert ExportRow list to list of dicts for JSON response."""
    return [r.model_dump() for r in rows]
