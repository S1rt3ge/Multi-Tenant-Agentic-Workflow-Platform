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
from uuid import UUID

from fastapi import APIRouter, Depends, Query, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_platform_admin, require_role
from app.models.user import User
from app.schemas.analytics import (
    DispatchAlertChannelCredentialCreate,
    DispatchAlertChannelCredentialListResponse,
    DispatchAlertChannelCredentialResponse,
    DispatchAlertDeliveryListResponse,
    DispatchAlertDeliveryResponse,
    DispatchAutomationPlanCreate,
    DispatchAutomationPlanListResponse,
    DispatchAutomationPlanReject,
    DispatchAutomationPlanResponse,
    DispatchAutomationWorkerConfig,
    DispatchAutomationWorkerDiagnosticsResponse,
    DispatchAutomationWorkerFleetDiagnosticsResponse,
    DispatchAutomationWorkerRunListResponse,
    DispatchAutomationWorkerRunResponse,
    DispatchControlRecommendationsResponse,
    DispatchIncidentAcknowledgementCreate,
    DispatchIncidentAcknowledgementResponse,
    DispatchIncidentAcknowledgementState,
    DispatchIncidentAnalyticsResponse,
    DispatchIncidentHistoryResponse,
    DispatchIncidentResolutionCreate,
    DispatchAlertPolicy,
    DispatchAlertPolicyPreview,
    DispatchHealthResponse,
    OverviewResponse,
    CostTimelineItem,
    WorkflowBreakdownItem,
)
from app.services import analytics_service
from app.services.dispatch_automation_plan_worker import run_dispatch_automation_plan_worker_once
from app.services.dispatch_automation_worker_scheduler import (
    inspect_dispatch_automation_scheduler_fleet,
)

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


@router.get("/dispatch-health", response_model=DispatchHealthResponse)
async def dispatch_health(
    window_hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Aggregate operator health for durable webhook dispatch."""
    return await analytics_service.get_dispatch_health(
        db=db,
        tenant_id=current_user.tenant_id,
        window_hours=window_hours,
    )


@router.get("/dispatch-alert-policy", response_model=DispatchAlertPolicy)
async def get_dispatch_alert_policy(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Read the tenant dispatch alert routing policy."""
    return await analytics_service.get_dispatch_alert_policy(
        db=db,
        tenant_id=current_user.tenant_id,
    )


@router.put("/dispatch-alert-policy", response_model=DispatchAlertPolicy)
async def update_dispatch_alert_policy(
    data: DispatchAlertPolicy,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "editor")),
):
    """Update the tenant dispatch alert routing policy."""
    return await analytics_service.update_dispatch_alert_policy(
        db=db,
        tenant_id=current_user.tenant_id,
        policy=data,
    )


@router.post("/dispatch-alert-policy/preview", response_model=DispatchAlertPolicyPreview)
async def preview_dispatch_alert_policy(
    window_hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Dry-run dispatch alert routing without sending notifications."""
    return await analytics_service.preview_dispatch_alert_policy(
        db=db,
        tenant_id=current_user.tenant_id,
        window_hours=window_hours,
    )


@router.post(
    "/dispatch-alert-channels",
    response_model=DispatchAlertChannelCredentialResponse,
    status_code=201,
)
async def create_dispatch_alert_channel(
    data: DispatchAlertChannelCredentialCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "editor")),
):
    """Create encrypted credentials for dispatch alert delivery."""
    return await analytics_service.create_dispatch_alert_channel(
        db=db,
        tenant_id=current_user.tenant_id,
        user_id=current_user.id,
        data=data,
    )


@router.get(
    "/dispatch-alert-channels",
    response_model=DispatchAlertChannelCredentialListResponse,
)
async def list_dispatch_alert_channels(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List non-secret dispatch alert delivery channel previews."""
    return await analytics_service.list_dispatch_alert_channels(
        db=db,
        tenant_id=current_user.tenant_id,
    )


@router.post(
    "/dispatch-alert-deliveries",
    response_model=DispatchAlertDeliveryResponse,
)
async def deliver_dispatch_alerts(
    window_hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "editor")),
):
    """Deliver current dispatch alerts to credential-backed policy channels."""
    return await analytics_service.deliver_dispatch_alerts(
        db=db,
        tenant_id=current_user.tenant_id,
        window_hours=window_hours,
    )


@router.get(
    "/dispatch-alert-deliveries",
    response_model=DispatchAlertDeliveryListResponse,
)
async def list_dispatch_alert_deliveries(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List recent sanitized dispatch alert delivery audit rows."""
    return await analytics_service.list_dispatch_alert_deliveries(
        db=db,
        tenant_id=current_user.tenant_id,
        limit=limit,
    )


@router.get("/dispatch-runbook", response_model=None)
async def dispatch_runbook(
    format: str = Query("json", pattern="^(json|markdown)$"),
    window_hours: int = Query(24, ge=1, le=720),
    delivery_limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return or export a sanitized dispatch incident handoff runbook."""
    runbook = await analytics_service.get_dispatch_runbook(
        db=db,
        tenant_id=current_user.tenant_id,
        window_hours=window_hours,
        delivery_limit=delivery_limit,
    )
    if format == "markdown":
        markdown = analytics_service.render_dispatch_runbook_markdown(runbook)
        return StreamingResponse(
            iter([markdown]),
            media_type="text/markdown",
            headers={"Content-Disposition": "attachment; filename=dispatch_runbook.md"},
        )
    return runbook


@router.get(
    "/dispatch-incident-acknowledgement",
    response_model=DispatchIncidentAcknowledgementState,
)
async def get_dispatch_incident_acknowledgement(
    window_hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Read acknowledgement state for the current dispatch incident."""
    return await analytics_service.get_dispatch_incident_acknowledgement(
        db=db,
        tenant_id=current_user.tenant_id,
        window_hours=window_hours,
    )


@router.post(
    "/dispatch-incident-acknowledgement",
    response_model=DispatchIncidentAcknowledgementResponse,
    status_code=201,
)
async def acknowledge_dispatch_incident(
    data: DispatchIncidentAcknowledgementCreate,
    window_hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "editor")),
):
    """Assign ownership for the current active dispatch incident."""
    return await analytics_service.acknowledge_dispatch_incident(
        db=db,
        tenant_id=current_user.tenant_id,
        user=current_user,
        data=data,
        window_hours=window_hours,
    )


@router.post(
    "/dispatch-incident-acknowledgement/resolve",
    response_model=DispatchIncidentAcknowledgementResponse,
)
async def resolve_dispatch_incident(
    data: DispatchIncidentResolutionCreate,
    window_hours: int = Query(24, ge=1, le=720),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "editor")),
):
    """Resolve the current acknowledged dispatch incident."""
    return await analytics_service.resolve_dispatch_incident(
        db=db,
        tenant_id=current_user.tenant_id,
        user=current_user,
        data=data,
        window_hours=window_hours,
    )


@router.get(
    "/dispatch-automation-plans",
    response_model=DispatchAutomationPlanListResponse,
)
async def list_dispatch_automation_plans(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List tenant-scoped approval-gated dispatch automation plans."""
    return await analytics_service.list_dispatch_automation_plans(
        db=db,
        tenant_id=current_user.tenant_id,
        limit=limit,
    )


@router.get(
    "/dispatch-automation-worker/config",
    response_model=DispatchAutomationWorkerConfig,
)
async def get_dispatch_automation_worker_config(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Read the tenant dispatch automation worker schedule config."""
    return await analytics_service.get_dispatch_automation_worker_config(
        db=db,
        tenant_id=current_user.tenant_id,
    )


@router.put(
    "/dispatch-automation-worker/config",
    response_model=DispatchAutomationWorkerConfig,
)
async def update_dispatch_automation_worker_config(
    data: DispatchAutomationWorkerConfig,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner")),
):
    """Update owner-gated dispatch automation worker schedule config."""
    return await analytics_service.update_dispatch_automation_worker_config(
        db=db,
        tenant_id=current_user.tenant_id,
        config=data,
    )


@router.get(
    "/dispatch-automation-worker/diagnostics",
    response_model=DispatchAutomationWorkerDiagnosticsResponse,
)
async def get_dispatch_automation_worker_diagnostics(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner")),
):
    """Read tenant-scoped scheduler diagnostics without mutating automation state."""
    settings = get_settings()
    return await analytics_service.get_dispatch_automation_worker_diagnostics(
        db=db,
        tenant_id=current_user.tenant_id,
        scheduler_enabled=settings.DISPATCH_AUTOMATION_WORKER_ENABLED,
        scheduler_interval_seconds=settings.DISPATCH_AUTOMATION_WORKER_INTERVAL_SECONDS,
        scheduler_tenant_limit=settings.DISPATCH_AUTOMATION_WORKER_TENANT_LIMIT,
    )


@router.get(
    "/dispatch-automation-worker/fleet",
    response_model=DispatchAutomationWorkerFleetDiagnosticsResponse,
)
async def get_dispatch_automation_worker_fleet(
    include_tenants: bool = Query(True),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_platform_admin),
):
    """Read cross-tenant scheduler fleet diagnostics for platform admins only."""
    settings = get_settings()
    snapshot = await inspect_dispatch_automation_scheduler_fleet(
        db=db,
        scheduler_enabled=settings.DISPATCH_AUTOMATION_WORKER_ENABLED,
        scheduler_interval_seconds=settings.DISPATCH_AUTOMATION_WORKER_INTERVAL_SECONDS,
        scheduler_tenant_limit=settings.DISPATCH_AUTOMATION_WORKER_TENANT_LIMIT,
        include_tenants=include_tenants,
    )
    return DispatchAutomationWorkerFleetDiagnosticsResponse.model_validate(snapshot)


@router.get(
    "/dispatch-automation-worker/runs",
    response_model=DispatchAutomationWorkerRunListResponse,
)
async def list_dispatch_automation_worker_runs(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List recent sanitized dispatch automation worker run audit rows."""
    return await analytics_service.list_dispatch_automation_worker_runs(
        db=db,
        tenant_id=current_user.tenant_id,
        limit=limit,
    )


@router.post(
    "/dispatch-automation-worker/run",
    response_model=DispatchAutomationWorkerRunResponse,
)
async def run_dispatch_automation_worker(
    limit: int = Query(10, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner")),
):
    """Run the dispatch automation worker once for the current tenant."""
    result = await run_dispatch_automation_plan_worker_once(
        db=db,
        limit=limit,
        tenant_id=current_user.tenant_id,
    )
    audit_run = await analytics_service.record_dispatch_automation_worker_run(
        db=db,
        tenant_id=current_user.tenant_id,
        trigger_type="manual",
        run_limit=limit,
        claimed=result.claimed,
        executed=result.executed,
        blocked=result.blocked,
        failed=result.failed,
        triggered_by=current_user.id,
    )
    return DispatchAutomationWorkerRunResponse(
        run_id=audit_run.id,
        claimed=result.claimed,
        executed=result.executed,
        blocked=result.blocked,
        failed=result.failed,
    )


@router.post(
    "/dispatch-automation-plans",
    response_model=DispatchAutomationPlanResponse,
    status_code=201,
)
async def create_dispatch_automation_plan(
    data: DispatchAutomationPlanCreate,
    window_hours: int = Query(24, ge=1, le=720),
    sla_minutes: int = Query(60, ge=1, le=10080),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner", "editor")),
):
    """Materialize a current dispatch automation recommendation as a dry-run approval plan."""
    return await analytics_service.create_dispatch_automation_plan(
        db=db,
        tenant_id=current_user.tenant_id,
        user=current_user,
        data=data,
        window_hours=window_hours,
        sla_minutes=sla_minutes,
    )


@router.post(
    "/dispatch-automation-plans/{plan_id}/approve",
    response_model=DispatchAutomationPlanResponse,
)
async def approve_dispatch_automation_plan(
    plan_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner")),
):
    """Approve an automation plan without executing automation."""
    return await analytics_service.approve_dispatch_automation_plan(
        db=db,
        tenant_id=current_user.tenant_id,
        user=current_user,
        plan_id=plan_id,
    )


@router.post(
    "/dispatch-automation-plans/{plan_id}/reject",
    response_model=DispatchAutomationPlanResponse,
)
async def reject_dispatch_automation_plan(
    plan_id: UUID,
    data: DispatchAutomationPlanReject,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role("owner")),
):
    """Reject an automation plan without executing automation."""
    return await analytics_service.reject_dispatch_automation_plan(
        db=db,
        tenant_id=current_user.tenant_id,
        user=current_user,
        plan_id=plan_id,
        data=data,
    )


@router.get(
    "/dispatch-control-recommendations",
    response_model=DispatchControlRecommendationsResponse,
)
async def dispatch_control_recommendations(
    window_hours: int = Query(24, ge=1, le=720),
    sla_minutes: int = Query(60, ge=1, le=10080),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return dry-run dispatch control automation recommendations."""
    return await analytics_service.get_dispatch_control_recommendations(
        db=db,
        tenant_id=current_user.tenant_id,
        window_hours=window_hours,
        sla_minutes=sla_minutes,
    )


@router.get(
    "/dispatch-incident-analytics",
    response_model=DispatchIncidentAnalyticsResponse,
)
async def dispatch_incident_analytics(
    days: int = Query(30, ge=1, le=365),
    sla_minutes: int = Query(60, ge=1, le=10080),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Return tenant-scoped dispatch incident trends and SLA metrics."""
    return await analytics_service.get_dispatch_incident_analytics(
        db=db,
        tenant_id=current_user.tenant_id,
        days=days,
        sla_minutes=sla_minutes,
    )


@router.get(
    "/dispatch-incident-history",
    response_model=DispatchIncidentHistoryResponse,
)
async def list_dispatch_incident_history(
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List sanitized incident acknowledgement/resolution history."""
    return await analytics_service.list_dispatch_incident_history(
        db=db,
        tenant_id=current_user.tenant_id,
        limit=limit,
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
