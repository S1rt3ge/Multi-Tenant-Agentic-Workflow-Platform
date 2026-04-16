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

from sqlalchemy import select, func, case, extract, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution import Execution
from app.models.workflow import Workflow
from app.schemas.analytics import (
    OverviewResponse,
    CostTimelineItem,
    WorkflowBreakdownItem,
    ExportRow,
)

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

    # Compute average duration per workflow (separate query for cross-DB compat)
    if items:
        for item in items:
            dur_stmt = (
                select(
                    Execution.started_at,
                    Execution.completed_at,
                )
                .where(
                    and_(
                        Execution.tenant_id == tenant_id,
                        Execution.workflow_id == uuid.UUID(item.workflow_id),
                        Execution.created_at >= period_start,
                        Execution.started_at.isnot(None),
                        Execution.completed_at.isnot(None),
                    )
                )
            )
            dur_result = await db.execute(dur_stmt)
            dur_rows = dur_result.all()
            if dur_rows:
                durations = []
                for dr in dur_rows:
                    if dr.started_at and dr.completed_at:
                        delta = (dr.completed_at - dr.started_at).total_seconds()
                        durations.append(delta)
                if durations:
                    item.avg_duration_sec = round(
                        sum(durations) / len(durations), 2
                    )

    _set_cached(cache_key, items)
    return items


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
            tokens=r.tokens,
            cost=round(float(r.cost), 4),
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
