"""Pydantic schemas for M6 — Dashboard & Analytics."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

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


class DispatchHealthAlert(BaseModel):
    """Aggregate operator alert for webhook dispatch health."""

    code: str
    severity: str
    title: str
    message: str
    count: int


class DispatchHealthResponse(BaseModel):
    """Aggregate health metrics for durable webhook dispatch."""

    paused_workflows: int = 0
    throttled_triggers: int = 0
    pending_dispatches: int = 0
    deferred_retries: int = 0
    dead_lettered_executions: int = 0
    manual_retries: int = 0
    alerts: list[DispatchHealthAlert] = []


DispatchAlertSeverity = Literal["critical", "warning", "info"]
DispatchAlertCode = Literal[
    "dispatch_paused",
    "trigger_throttled",
    "deferred_retries",
    "dead_lettered",
]


class DispatchAlertChannel(BaseModel):
    """Non-secret destination descriptor for dry-run alert routing."""

    type: Literal["email", "slack", "webhook"]
    target: str = Field(..., min_length=3, max_length=500)
    credential_id: UUID | None = None
    enabled: bool = True


class DispatchAlertPolicy(BaseModel):
    """Tenant policy for routing dispatch health alerts."""

    enabled: bool = False
    channels: list[DispatchAlertChannel] = Field(default_factory=list, max_length=10)
    severities: list[DispatchAlertSeverity] = Field(
        default_factory=lambda: ["critical", "warning"],
        min_length=1,
    )
    alert_codes: list[DispatchAlertCode] = Field(
        default_factory=lambda: [
            "dispatch_paused",
            "trigger_throttled",
            "dead_lettered",
        ],
        min_length=1,
    )
    cooldown_minutes: int = Field(30, ge=5, le=1440)


class DispatchAlertPolicyPreviewRoute(BaseModel):
    """A planned destination for a dry-run alert preview."""

    channel_type: str
    target: str
    alert_codes: list[str]


class DispatchAlertPolicyPreview(BaseModel):
    """Dry-run preview of alert routing without external delivery."""

    dry_run: bool = True
    policy_enabled: bool
    alerts: list[DispatchHealthAlert]
    routes: list[DispatchAlertPolicyPreviewRoute]


class DispatchAlertChannelCredentialCreate(BaseModel):
    """Create encrypted channel credentials for alert delivery."""

    name: str = Field(..., min_length=1, max_length=120)
    channel_type: Literal["webhook"]
    config: dict = Field(default_factory=dict)


class DispatchAlertChannelCredentialResponse(BaseModel):
    """Non-secret channel credential preview."""

    id: UUID
    name: str
    channel_type: str
    config_preview: dict
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class DispatchAlertChannelCredentialListResponse(BaseModel):
    items: list[DispatchAlertChannelCredentialResponse]


class DispatchAlertDeliveryItem(BaseModel):
    id: UUID
    alert_code: str
    channel_type: str
    target_preview: str
    status: str
    status_code: int | None = None
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DispatchAlertDeliveryResponse(BaseModel):
    attempted: int
    delivered: int
    failed: int
    skipped: int
    items: list[DispatchAlertDeliveryItem]


class DispatchAlertDeliveryListResponse(BaseModel):
    items: list[DispatchAlertDeliveryItem]


class DispatchRunbookPolicy(BaseModel):
    enabled: bool
    configured_channels: int
    cooldown_minutes: int


class DispatchRunbookAction(BaseModel):
    title: str
    detail: str
    priority: DispatchAlertSeverity


class DispatchIncidentAcknowledgementCreate(BaseModel):
    note: str | None = Field(None, max_length=1000)


class DispatchIncidentResolutionCreate(BaseModel):
    resolution_note: str | None = Field(None, max_length=2000)


class DispatchIncidentAcknowledgementResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    incident_key: str
    status: str
    severity: str
    summary: str
    alert_codes: list[str]
    acknowledged_by: UUID | None = None
    acknowledged_by_email: str
    acknowledged_by_name: str | None = None
    note: str | None = None
    resolved_by: UUID | None = None
    resolved_by_email: str | None = None
    resolved_by_name: str | None = None
    resolution_note: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DispatchIncidentAcknowledgementState(BaseModel):
    acknowledgement: DispatchIncidentAcknowledgementResponse | None = None


class DispatchIncidentHistoryResponse(BaseModel):
    items: list[DispatchIncidentAcknowledgementResponse]


class DispatchIncidentTrendItem(BaseModel):
    day: str
    acknowledged: int = 0
    resolved: int = 0
    open: int = 0
    sla_breaches: int = 0


class DispatchIncidentSeverityBreakdownItem(BaseModel):
    severity: str
    total_incidents: int = 0
    resolved_incidents: int = 0
    open_incidents: int = 0
    sla_breaches: int = 0
    avg_resolution_minutes: float | None = None


class DispatchIncidentAnalyticsResponse(BaseModel):
    generated_at: datetime
    window_days: int
    sla_minutes: int
    total_incidents: int = 0
    resolved_incidents: int = 0
    open_incidents: int = 0
    sla_breaches: int = 0
    sla_breach_rate: float = 0.0
    avg_resolution_minutes: float | None = None
    trends: list[DispatchIncidentTrendItem] = []
    by_severity: list[DispatchIncidentSeverityBreakdownItem] = []


class DispatchAutomationRecommendation(BaseModel):
    code: str
    priority: DispatchAlertSeverity
    title: str
    rationale: str
    suggested_action: str
    automation_type: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: list[str] = []
    blocked_by: list[str] = []


class DispatchControlRecommendationsResponse(BaseModel):
    generated_at: datetime
    dry_run: bool = True
    window_hours: int
    sla_minutes: int
    recommendation_count: int = 0
    automation_ready_count: int = 0
    recommendations: list[DispatchAutomationRecommendation] = []


class DispatchAutomationPlanCreate(BaseModel):
    recommendation_code: str = Field(..., min_length=1, max_length=120)


class DispatchAutomationPlanReject(BaseModel):
    rejection_note: str | None = Field(None, max_length=2000)


class DispatchAutomationPlanResponse(BaseModel):
    id: UUID
    tenant_id: UUID
    recommendation_code: str
    automation_type: str
    status: str
    priority: str
    title: str
    rationale: str
    suggested_action: str
    confidence: float
    evidence: list[str]
    blocked_by: list[str]
    dry_run: bool = True
    requested_by: UUID | None = None
    requested_by_email: str
    requested_by_name: str | None = None
    approved_by: UUID | None = None
    approved_by_email: str | None = None
    approved_by_name: str | None = None
    approved_at: datetime | None = None
    rejected_by: UUID | None = None
    rejected_by_email: str | None = None
    rejected_by_name: str | None = None
    rejected_at: datetime | None = None
    execution_result: dict = {}
    executed_at: datetime | None = None
    execution_error: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DispatchAutomationPlanListResponse(BaseModel):
    items: list[DispatchAutomationPlanResponse]


class DispatchAutomationWorkerConfig(BaseModel):
    enabled: bool = False
    interval_minutes: int = Field(15, ge=5, le=1440)
    max_plans_per_run: int = Field(10, ge=1, le=50)


class DispatchAutomationWorkerRunItem(BaseModel):
    id: UUID
    trigger_type: str
    status: str
    limit: int
    claimed: int = 0
    executed: int = 0
    blocked: int = 0
    failed: int = 0
    error_message: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class DispatchAutomationWorkerRunListResponse(BaseModel):
    items: list[DispatchAutomationWorkerRunItem]


class DispatchAutomationWorkerDiagnosticsResponse(BaseModel):
    generated_at: datetime
    scheduler_enabled: bool
    scheduler_interval_seconds: float
    scheduler_tenant_limit: int
    tenant_config: DispatchAutomationWorkerConfig
    approved_plan_count: int = 0
    latest_scheduled_run: DispatchAutomationWorkerRunItem | None = None
    tenant_due_now: bool = False
    tenant_skip_reason: str | None = None
    next_run_at: datetime | None = None
    backoff_until: datetime | None = None


class DispatchAutomationWorkerFleetTenantSummary(BaseModel):
    tenant_id: str
    enabled: bool
    due_now: bool
    skip_reason: str | None = None
    approved_plan_count: int = 0
    latest_scheduled_status: str | None = None
    last_scheduled_at: datetime | None = None
    next_run_at: datetime | None = None
    backoff_until: datetime | None = None
    max_plans_per_run: int = 10

    model_config = {"from_attributes": True}


class DispatchAutomationWorkerFleetDiagnosticsResponse(BaseModel):
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
    tenants: list[DispatchAutomationWorkerFleetTenantSummary] = []

    model_config = {"from_attributes": True}


class DispatchAutomationWorkerRunResponse(BaseModel):
    run_id: UUID | None = None
    claimed: int = 0
    executed: int = 0
    blocked: int = 0
    failed: int = 0


class DispatchRunbookResponse(BaseModel):
    tenant_id: UUID
    generated_at: datetime
    window_hours: int
    severity: DispatchAlertSeverity
    summary: str
    health: DispatchHealthResponse
    policy: DispatchRunbookPolicy
    alerts: list[DispatchHealthAlert]
    recent_deliveries: list[DispatchAlertDeliveryItem]
    recommended_actions: list[DispatchRunbookAction]
    acknowledgement: DispatchIncidentAcknowledgementResponse | None = None
    incident_history: list[DispatchIncidentAcknowledgementResponse] = []


class ExportRow(BaseModel):
    """Single row in the export."""

    execution_id: str
    workflow_name: str
    status: str
    tokens: int
    cost: float
    started_at: str | None = None
    completed_at: str | None = None
