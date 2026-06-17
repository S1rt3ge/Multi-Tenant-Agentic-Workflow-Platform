"""Tests for M12 approval-gated dispatch automation execution worker."""

import uuid

import pytest
from sqlalchemy import select

from app.models.dispatch_alert import DispatchAutomationPlan
from app.models.execution import Execution
from app.models.workflow import Workflow
from app.services.dispatch_automation_plan_worker import (
    run_dispatch_automation_plan_worker_once,
)


async def _create_workflow(
    db_session,
    tenant_id: uuid.UUID,
    *,
    dispatch_paused: bool = True,
) -> Workflow:
    workflow = Workflow(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        name="Automation Worker WF",
        description="automation worker test",
        definition={"nodes": [{"id": "secret-node", "data": {"token": "secret-workflow-token"}}]},
        dispatch_paused=dispatch_paused,
    )
    db_session.add(workflow)
    await db_session.commit()
    await db_session.refresh(workflow)
    return workflow


async def _create_dead_letter_execution(
    db_session,
    tenant_id: uuid.UUID,
    workflow_id: uuid.UUID,
) -> Execution:
    execution = Execution(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        status="failed",
        input_data={
            "trigger": {"type": "webhook"},
            "payload": {"lead_id": "secret-lead"},
            "headers": {"x-webhook-secret": "secret-webhook-header"},
            "dispatch": {
                "attempt": 3,
                "dead_lettered": True,
                "dead_letter_reason": "max_attempts_exhausted",
            },
        },
    )
    db_session.add(execution)
    await db_session.commit()
    await db_session.refresh(execution)
    return execution


async def _create_plan(
    db_session,
    tenant_id: uuid.UUID,
    *,
    automation_type: str = "resume_guard",
    status: str = "approved",
    recommendation_code: str = "auto_resume_guard",
) -> DispatchAutomationPlan:
    plan = DispatchAutomationPlan(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        recommendation_code=recommendation_code,
        automation_type=automation_type,
        status=status,
        priority="warning",
        title="Add a guarded dispatch resume workflow",
        rationale="Paused workflow dispatch can linger after recovery.",
        suggested_action="Resume paused dispatch only when current health is safe.",
        confidence=0.82,
        evidence=["1 paused workflow dispatch queue"],
        blocked_by=[],
        requested_by_email="owner@test.com",
    )
    db_session.add(plan)
    await db_session.commit()
    await db_session.refresh(plan)
    return plan


@pytest.mark.asyncio
async def test_worker_executes_approved_resume_guard_when_health_is_safe(
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    workflow = await _create_workflow(db_session, tenant_id, dispatch_paused=True)
    plan = await _create_plan(db_session, tenant_id)

    result = await run_dispatch_automation_plan_worker_once(db_session, limit=10)

    assert result.claimed == 1
    assert result.executed == 1
    assert result.blocked == 0
    await db_session.refresh(workflow)
    await db_session.refresh(plan)
    assert workflow.dispatch_paused is False
    assert plan.status == "executed"
    assert plan.executed_at is not None
    assert plan.execution_result["resumed_workflows"] == 1
    serialized = str(plan.execution_result)
    assert "secret-workflow-token" not in serialized
    assert "secret-webhook-header" not in serialized


@pytest.mark.asyncio
async def test_worker_executes_approved_dead_letter_retry_plan_without_exposing_payloads(
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    workflow = await _create_workflow(db_session, tenant_id, dispatch_paused=False)
    source = await _create_dead_letter_execution(db_session, tenant_id, workflow.id)
    plan = await _create_plan(
        db_session,
        tenant_id,
        automation_type="approval_gated_retry",
        recommendation_code="auto_retry_dead_letters",
    )

    result = await run_dispatch_automation_plan_worker_once(db_session, limit=10)

    assert result.claimed == 1
    assert result.executed == 1
    assert result.blocked == 0
    await db_session.refresh(source)
    await db_session.refresh(plan)
    assert source.status == "failed"
    assert source.input_data["dispatch"]["dead_lettered"] is True
    assert plan.status == "executed"
    assert plan.execution_result["action"] == "approval_gated_retry"
    assert plan.execution_result["retried_executions"] == 1

    execution_result = await db_session.execute(
        select(Execution)
        .where(Execution.tenant_id == tenant_id)
        .order_by(Execution.created_at.asc())
    )
    retry_executions = [
        execution
        for execution in execution_result.scalars().all()
        if execution.id != source.id
    ]
    assert len(retry_executions) == 1
    retry = retry_executions[0]
    assert plan.execution_result["retry_execution_ids"] == [str(retry.id)]
    assert retry.status == "pending"
    assert retry.workflow_id == source.workflow_id
    assert retry.tenant_id == source.tenant_id
    assert retry.input_data["trigger"]["type"] == "webhook"
    assert retry.input_data["payload"] == {"lead_id": "secret-lead"}
    dispatch = retry.input_data["dispatch"]
    assert dispatch["attempt"] == 4
    assert dispatch["manual_retry"] is True
    assert dispatch["automated_retry"] is True
    assert dispatch["automation_plan_id"] == str(plan.id)
    assert dispatch["parent_execution_id"] == str(source.id)
    assert dispatch["previous_execution_id"] == str(source.id)
    assert dispatch["dead_lettered"] is False
    assert "dead_letter_reason" not in dispatch
    serialized = str(plan.execution_result)
    assert "secret-lead" not in serialized
    assert "secret-webhook-header" not in serialized


@pytest.mark.asyncio
async def test_worker_blocks_retry_plan_without_eligible_dead_letters(
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    await _create_workflow(db_session, tenant_id, dispatch_paused=False)
    plan = await _create_plan(
        db_session,
        tenant_id,
        automation_type="approval_gated_retry",
        recommendation_code="auto_retry_dead_letters",
    )

    result = await run_dispatch_automation_plan_worker_once(db_session, limit=10)

    assert result.claimed == 1
    assert result.executed == 0
    assert result.blocked == 1
    await db_session.refresh(plan)
    assert plan.status == "blocked"
    assert "eligible" in plan.execution_result["reason"]
    execution_result = await db_session.execute(
        select(Execution).where(Execution.tenant_id == tenant_id)
    )
    assert len(list(execution_result.scalars().all())) == 0


@pytest.mark.asyncio
async def test_worker_skips_dead_letter_source_that_already_has_retry_child(
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    workflow = await _create_workflow(db_session, tenant_id, dispatch_paused=False)
    source = await _create_dead_letter_execution(db_session, tenant_id, workflow.id)
    db_session.add(
        Execution(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            workflow_id=workflow.id,
            status="pending",
            input_data={
                "trigger": {"type": "webhook"},
                "dispatch": {
                    "manual_retry": True,
                    "parent_execution_id": str(source.id),
                    "previous_execution_id": str(source.id),
                    "dead_lettered": False,
                },
            },
        )
    )
    await db_session.commit()
    plan = await _create_plan(
        db_session,
        tenant_id,
        automation_type="approval_gated_retry",
        recommendation_code="auto_retry_dead_letters",
    )

    result = await run_dispatch_automation_plan_worker_once(db_session, limit=10)

    assert result.claimed == 1
    assert result.executed == 0
    assert result.blocked == 1
    await db_session.refresh(plan)
    assert plan.status == "blocked"
    assert "eligible" in plan.execution_result["reason"]
    execution_result = await db_session.execute(
        select(Execution).where(Execution.tenant_id == tenant_id)
    )
    assert len(list(execution_result.scalars().all())) == 2


@pytest.mark.asyncio
async def test_worker_blocks_resume_guard_when_dispatch_health_is_unsafe(
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    workflow = await _create_workflow(db_session, tenant_id, dispatch_paused=True)
    await _create_dead_letter_execution(db_session, tenant_id, workflow.id)
    plan = await _create_plan(db_session, tenant_id)

    result = await run_dispatch_automation_plan_worker_once(db_session, limit=10)

    assert result.claimed == 1
    assert result.executed == 0
    assert result.blocked == 1
    await db_session.refresh(workflow)
    await db_session.refresh(plan)
    assert workflow.dispatch_paused is True
    assert plan.status == "blocked"
    assert "dead_lettered" in plan.execution_result["reason"]
    serialized = str(plan.execution_result)
    assert "secret-lead" not in serialized
    assert "secret-webhook-header" not in serialized


@pytest.mark.asyncio
async def test_worker_blocks_unsupported_automation_types_and_skips_terminal_plans(
    registered_user,
    db_session,
):
    tenant_id = uuid.UUID(registered_user["tenant_id"])
    await _create_workflow(db_session, tenant_id, dispatch_paused=True)
    unsupported = await _create_plan(
        db_session,
        tenant_id,
        automation_type="rate_limit_tuning",
        recommendation_code="auto_rate_limit_tuning",
    )
    terminal = await _create_plan(
        db_session,
        tenant_id,
        status="executed",
        recommendation_code="auto_resume_guard_terminal",
    )
    terminal.execution_result = {"already": "done"}
    db_session.add(terminal)
    await db_session.commit()

    first = await run_dispatch_automation_plan_worker_once(db_session, limit=10)
    second = await run_dispatch_automation_plan_worker_once(db_session, limit=10)

    assert first.claimed == 1
    assert first.blocked == 1
    assert second.claimed == 0
    await db_session.refresh(unsupported)
    await db_session.refresh(terminal)
    assert unsupported.status == "blocked"
    assert unsupported.execution_result["reason"] == "Unsupported automation type."
    assert terminal.status == "executed"
    assert terminal.execution_result == {"already": "done"}
