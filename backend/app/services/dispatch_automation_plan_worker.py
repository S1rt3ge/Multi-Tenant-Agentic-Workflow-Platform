"""Approval-gated dispatch automation plan worker."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.dispatch_alert import DispatchAutomationPlan
from app.models.execution import Execution
from app.models.workflow import Workflow
from app.services.analytics_service import get_dispatch_health
from app.services.connector_security import sanitize_error
from app.services.execution_service import retry_dead_letter_execution


TERMINAL_PLAN_STATUSES = {"executed", "blocked", "failed", "rejected"}


@dataclass(slots=True)
class DispatchAutomationWorkerResult:
    claimed: int = 0
    executed: int = 0
    blocked: int = 0
    failed: int = 0


def _safe_result(data: dict) -> dict:
    safe: dict = {}
    for key, value in data.items():
        if isinstance(value, str):
            safe[key] = sanitize_error(value)
        elif isinstance(value, list):
            safe[key] = [sanitize_error(item) if isinstance(item, str) else item for item in value]
        elif isinstance(value, dict):
            safe[key] = _safe_result(value)
        else:
            safe[key] = value
    return safe


def _dispatch_metadata(execution: Execution) -> dict:
    input_data = execution.input_data if isinstance(execution.input_data, dict) else {}
    dispatch = input_data.get("dispatch") if isinstance(input_data.get("dispatch"), dict) else {}
    return dispatch or {}


def _is_eligible_dead_letter_source(execution: Execution) -> bool:
    input_data = execution.input_data if isinstance(execution.input_data, dict) else {}
    trigger = input_data.get("trigger") if isinstance(input_data.get("trigger"), dict) else {}
    dispatch = _dispatch_metadata(execution)
    return (
        execution.status == "failed"
        and trigger.get("type") == "webhook"
        and dispatch.get("dead_lettered") is True
    )


def _retry_child_source_ids(executions: list[Execution]) -> set[str]:
    source_ids: set[str] = set()
    for execution in executions:
        dispatch = _dispatch_metadata(execution)
        source_id = dispatch.get("parent_execution_id") or dispatch.get("previous_execution_id")
        if source_id:
            source_ids.add(str(source_id))
    return source_ids


# Bound the dead-letter scan so an established tenant's full execution history is
# never loaded into memory. Only the most recent window is considered; older
# dead letters are treated as stale and not auto-retried.
MAX_DEAD_LETTER_SCAN = 1000


async def _find_dead_letter_retry_source(
    db: AsyncSession,
    plan: DispatchAutomationPlan,
) -> Execution | None:
    result = await db.execute(
        select(Execution)
        .where(Execution.tenant_id == plan.tenant_id)
        .order_by(Execution.created_at.desc(), Execution.id.desc())
        .limit(MAX_DEAD_LETTER_SCAN)
    )
    # Restore ascending order so the oldest eligible source within the window wins.
    executions = list(reversed(result.scalars().all()))
    retried_source_ids = _retry_child_source_ids(executions)
    for execution in executions:
        if str(execution.id) in retried_source_ids:
            continue
        if _is_eligible_dead_letter_source(execution):
            return execution
    return None


async def _execute_resume_guard(
    db: AsyncSession,
    plan: DispatchAutomationPlan,
) -> tuple[str, dict]:
    health = await get_dispatch_health(db=db, tenant_id=plan.tenant_id, window_hours=24)
    unsafe_reasons: list[str] = []
    if health.dead_lettered_executions:
        unsafe_reasons.append("dead_lettered dispatches remain active")
    if health.deferred_retries:
        unsafe_reasons.append("deferred retries remain active")
    if health.throttled_triggers:
        unsafe_reasons.append("throttled triggers remain active")

    if unsafe_reasons:
        return (
            "blocked",
            {
                "reason": sanitize_error(", ".join(unsafe_reasons)),
                "paused_workflows": health.paused_workflows,
                "dead_lettered_executions": health.dead_lettered_executions,
                "deferred_retries": health.deferred_retries,
                "throttled_triggers": health.throttled_triggers,
            },
        )

    result = await db.execute(
        select(Workflow).where(
            Workflow.tenant_id == plan.tenant_id,
            Workflow.dispatch_paused == True,  # noqa: E712
        )
    )
    workflows = list(result.scalars().all())
    for workflow in workflows:
        workflow.dispatch_paused = False
        db.add(workflow)

    return (
        "executed",
        {
            "action": "resume_guard",
            "resumed_workflows": len(workflows),
        },
    )


def _retry_actor_id(plan: DispatchAutomationPlan):
    return plan.approved_by or plan.requested_by or plan.id


async def _execute_approval_gated_retry(
    db: AsyncSession,
    plan: DispatchAutomationPlan,
) -> tuple[str, dict]:
    source = await _find_dead_letter_retry_source(db, plan)
    if source is None:
        return (
            "blocked",
            {
                "action": "approval_gated_retry",
                "reason": "No eligible dead-lettered webhook execution found.",
                "retried_executions": 0,
            },
        )

    try:
        retry = await retry_dead_letter_execution(
            db=db,
            tenant_id=plan.tenant_id,
            execution_id=source.id,
            requested_by_user_id=_retry_actor_id(plan),
        )
    except HTTPException as exc:
        return (
            "blocked",
            {
                "action": "approval_gated_retry",
                "reason": sanitize_error(str(exc.detail)),
                "retried_executions": 0,
                "source_execution_id": str(source.id),
            },
        )

    retry_input_data = deepcopy(retry.input_data or {})
    dispatch = deepcopy(retry_input_data.get("dispatch") or {})
    dispatch.update(
        {
            "automated_retry": True,
            "automation_plan_id": str(plan.id),
        }
    )
    retry_input_data["dispatch"] = dispatch
    retry.input_data = retry_input_data
    db.add(retry)
    await db.flush()

    return (
        "executed",
        {
            "action": "approval_gated_retry",
            "retried_executions": 1,
            "source_execution_ids": [str(source.id)],
            "retry_execution_ids": [str(retry.id)],
        },
    )


async def _execute_plan(
    db: AsyncSession,
    plan: DispatchAutomationPlan,
) -> tuple[str, dict]:
    if plan.automation_type == "resume_guard":
        return await _execute_resume_guard(db, plan)
    if plan.automation_type == "approval_gated_retry":
        return await _execute_approval_gated_retry(db, plan)
    return (
        "blocked",
        {
            "reason": "Unsupported automation type.",
            "automation_type": sanitize_error(plan.automation_type),
        },
    )


async def run_dispatch_automation_plan_worker_once(
    db: AsyncSession,
    limit: int = 10,
    tenant_id: UUID | None = None,
) -> DispatchAutomationWorkerResult:
    result = DispatchAutomationWorkerResult()
    query = select(DispatchAutomationPlan).where(DispatchAutomationPlan.status == "approved")
    if tenant_id is not None:
        query = query.where(DispatchAutomationPlan.tenant_id == tenant_id)
    plan_result = await db.execute(
        query
        .order_by(DispatchAutomationPlan.approved_at.asc().nulls_last(), DispatchAutomationPlan.created_at.asc())
        .limit(limit)
    )
    plans = list(plan_result.scalars().all())

    for plan in plans:
        if plan.status in TERMINAL_PLAN_STATUSES:
            continue
        result.claimed += 1
        plan.status = "executing"
        db.add(plan)
        await db.flush()

        try:
            status, execution_result = await _execute_plan(db, plan)
            plan.status = status
            plan.execution_result = _safe_result(execution_result)
            plan.executed_at = datetime.now(timezone.utc)
            plan.execution_error = None
            if status == "executed":
                result.executed += 1
            elif status == "blocked":
                result.blocked += 1
            else:
                result.failed += 1
        except Exception as exc:
            plan.status = "failed"
            plan.execution_result = {"reason": "Automation execution failed."}
            plan.execution_error = sanitize_error(str(exc))
            plan.executed_at = datetime.now(timezone.utc)
            result.failed += 1
        db.add(plan)

    await db.commit()
    return result
