"""
API routes for M6 — Dashboard & Analytics.

Endpoints:
  GET /analytics/overview        — KPI for current period
  GET /analytics/cost-timeline   — daily cost for last N days
  GET /analytics/workflow-breakdown — per-workflow cost breakdown
  GET /analytics/export          — export execution data as CSV or JSON
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.user import User
from app.schemas.analytics import (
    OverviewResponse,
    CostTimelineItem,
    WorkflowBreakdownItem,
)
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])


def _parse_iso_datetime(value: str, label: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid '{label}' date format. Use ISO format: YYYY-MM-DD",
        ) from exc

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


@router.get("/overview", response_model=OverviewResponse)
async def overview(
    period: str = Query("month", pattern="^(month|week)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """KPI overview: total executions, success/fail counts, tokens, cost, success rate."""
    return await analytics_service.get_overview(
        db=db,
        tenant_id=current_user.tenant_id,
        period=period,
    )


@router.get("/cost-timeline", response_model=list[CostTimelineItem])
async def cost_timeline(
    days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Daily cost + execution count for the last N days. Missing days filled with zeros."""
    return await analytics_service.get_cost_timeline(
        db=db,
        tenant_id=current_user.tenant_id,
        days=days,
    )


@router.get("/workflow-breakdown", response_model=list[WorkflowBreakdownItem])
async def workflow_breakdown(
    period: str = Query("month", pattern="^(month|week)$"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Per-workflow breakdown: runs, cost, avg duration, % of total cost."""
    return await analytics_service.get_workflow_breakdown(
        db=db,
        tenant_id=current_user.tenant_id,
        period=period,
    )


@router.get("/export")
async def export_data(
    format: str = Query("csv", pattern="^(csv|json)$"),
    from_date: str | None = Query(None, alias="from"),
    to_date: str | None = Query(None, alias="to"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Export execution data as CSV file download or JSON array.
    Query params: ?format=csv|json&from=ISO_DATE&to=ISO_DATE
    Max 50 000 rows.
    """
    # Parse dates
    parsed_from = None
    parsed_to = None

    if from_date:
        parsed_from = _parse_iso_datetime(from_date, "from")

    if to_date:
        parsed_to = _parse_iso_datetime(to_date, "to")

    if parsed_from and parsed_to and parsed_from > parsed_to:
        raise HTTPException(
            status_code=400,
            detail="'from' date must be less than or equal to 'to' date",
        )

    rows, fmt = await analytics_service.get_export_data(
        db=db,
        tenant_id=current_user.tenant_id,
        format=format,
        from_date=parsed_from,
        to_date=parsed_to,
    )

    if fmt == "csv":
        csv_content = analytics_service.export_rows_to_csv(rows)
        return StreamingResponse(
            iter([csv_content]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=executions_export.csv"},
        )
    else:
        # JSON format
        return analytics_service.export_rows_to_json(rows)
