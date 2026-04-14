"""Pydantic schemas for M6 — Dashboard & Analytics."""

from __future__ import annotations

from pydantic import BaseModel, Field


class OverviewResponse(BaseModel):
    """KPI overview for the current period."""

    total_executions: int = 0
    successful: int = 0
    failed: int = 0
    tokens_used: int = 0
    total_cost: float = 0.0
    success_rate: float | None = None  # None when total_executions == 0


class CostTimelineItem(BaseModel):
    """Single day in the cost timeline."""

    day: str  # ISO date string, e.g. "2026-04-14"
    daily_cost: float = 0.0
    executions_count: int = 0


class WorkflowBreakdownItem(BaseModel):
    """Cost breakdown for a single workflow."""

    workflow_id: str
    workflow_name: str
    runs: int = 0
    cost: float = 0.0
    avg_duration_sec: float | None = None
    cost_percentage: float = 0.0  # % of total cost


class ExportRow(BaseModel):
    """Single row in the export."""

    execution_id: str
    workflow_name: str
    status: str
    tokens: int
    cost: float
    started_at: str | None = None
    completed_at: str | None = None
