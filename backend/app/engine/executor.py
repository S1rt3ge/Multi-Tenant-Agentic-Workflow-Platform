"""
Workflow Executor: runs a compiled LangGraph workflow end-to-end.

Lifecycle:
1. Create Execution record (status: pending).
2. Check budget: tenant.tokens_used_this_month < tenant.monthly_token_budget.
3. Compile graph via compiler.
4. Set status: running, started_at.
5. Iterate through graph nodes, for each step:
   a. Execute agent via engine.agents.base.execute_agent.
   b. Record ExecutionLog.
   c. Update execution totals (total_tokens, total_cost).
   d. Update tenant.tokens_used_this_month.
   e. Send WebSocket event.
   f. Check budget — cancel if exceeded.
   g. Check cancellation flag.
6. Set status: completed/failed, output_data, completed_at.
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution import Execution, ExecutionLog
from app.models.tenant import Tenant
from app.models.workflow import Workflow
from app.engine.compiler import compile_graph, CompilationError, AgentState
from app.engine.agents.base import execute_agent

logger = logging.getLogger(__name__)

# Max iterations for cyclic graphs
MAX_ITERATIONS = 10

# Global dict of active executions for cancel support
# {execution_id (str): {"cancelled": bool}}
_active_executions: dict[str, dict] = {}

# Global dict of WebSocket connections per execution
# {execution_id (str): list[asyncio.Queue]}
_ws_subscribers: dict[str, list[asyncio.Queue]] = {}


def _log_execution_event(level: int, event: str, **fields) -> None:
    """Emit structured execution lifecycle logs."""
    logger.log(level, event, extra=fields)


# ---------------------------------------------------------------------------
# WebSocket helpers
# ---------------------------------------------------------------------------

def subscribe_ws(execution_id: str) -> asyncio.Queue:
    """Subscribe to WebSocket events for an execution."""
    if execution_id not in _ws_subscribers:
        _ws_subscribers[execution_id] = []
    queue: asyncio.Queue = asyncio.Queue()
    _ws_subscribers[execution_id].append(queue)
    return queue


def unsubscribe_ws(execution_id: str, queue: asyncio.Queue) -> None:
    """Unsubscribe from WebSocket events."""
    if execution_id in _ws_subscribers:
        try:
            _ws_subscribers[execution_id].remove(queue)
        except ValueError:
            pass
        if not _ws_subscribers[execution_id]:
            del _ws_subscribers[execution_id]


async def _broadcast_ws(execution_id: str, event: dict) -> None:
    """Broadcast a WebSocket event to all subscribers."""
    subscribers = _ws_subscribers.get(execution_id, [])
    for queue in subscribers:
        try:
            await queue.put(event)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Cancel support
# ---------------------------------------------------------------------------

def request_cancel(execution_id: str) -> bool:
    """Request cancellation of a running execution.

    Returns True if the execution was found and flagged.
    """
    key = str(execution_id)
    if key in _active_executions:
        _active_executions[key]["cancelled"] = True
        return True
    return False


def _is_cancelled(execution_id: str) -> bool:
    """Check if an execution has been flagged for cancellation."""
    key = str(execution_id)
    return _active_executions.get(key, {}).get("cancelled", False)


# ---------------------------------------------------------------------------
# Main executor
# ---------------------------------------------------------------------------

async def run_execution(
    execution_id: UUID,
    workflow_id: UUID,
    tenant_id: UUID,
    input_data: dict[str, Any] | None,
    db: AsyncSession,
) -> None:
    """Run a workflow execution asynchronously.

    This function is intended to be called as a background task.
    It manages the full lifecycle and updates the DB at each step.
    """
    exec_id_str = str(execution_id)
    _active_executions[exec_id_str] = {"cancelled": False}

    _log_execution_event(
        logging.INFO,
        "execution_started",
        execution_id=exec_id_str,
        workflow_id=str(workflow_id),
        tenant_id=str(tenant_id),
    )

    try:
        await _run_execution_inner(execution_id, workflow_id, tenant_id, input_data, db)
    except Exception as e:
        _log_execution_event(
            logging.ERROR,
            "execution_fatal_error",
            execution_id=exec_id_str,
            workflow_id=str(workflow_id),
            tenant_id=str(tenant_id),
            error=str(e),
        )
        try:
            await _fail_execution(db, execution_id, str(e))
            await _broadcast_ws(exec_id_str, {
                "type": "error",
                "data": {"message": str(e), "agent_name": "", "step_number": 0},
            })
        except Exception:
            pass
    finally:
        _active_executions.pop(exec_id_str, None)
        # Send final cleanup event to WS subscribers
        if exec_id_str in _ws_subscribers:
            # Subscribers will clean up on disconnect
            pass


async def _run_execution_inner(
    execution_id: UUID,
    workflow_id: UUID,
    tenant_id: UUID,
    input_data: dict[str, Any] | None,
    db: AsyncSession,
) -> None:
    """Inner execution logic."""
    exec_id_str = str(execution_id)

    # Load workflow
    wf_result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.tenant_id == tenant_id,
            Workflow.is_active == True,  # noqa: E712
        )
    )
    workflow = wf_result.scalar_one_or_none()
    if not workflow:
        raise Exception("Workflow not found or inactive")

    definition = workflow.definition
    if not definition or not definition.get("nodes"):
        raise Exception("Workflow has no nodes defined")

    # Check budget
    tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
    tenant = tenant_result.scalar_one_or_none()
    if not tenant:
        raise Exception("Tenant not found")

    if tenant.tokens_used_this_month >= tenant.monthly_token_budget:
        await _fail_execution(db, execution_id, "Monthly token budget exceeded")
        await _broadcast_ws(exec_id_str, {
            "type": "error",
            "data": {"message": "Monthly token budget exceeded", "agent_name": "", "step_number": 0},
        })
        return

    # Compile graph
    try:
        compiled_graph, agent_config_map = await compile_graph(
            definition, workflow_id, tenant_id, db
        )
    except CompilationError as e:
        await _fail_execution(db, execution_id, f"Compilation error: {str(e)}")
        await _broadcast_ws(exec_id_str, {
            "type": "error",
            "data": {"message": str(e), "agent_name": "", "step_number": 0},
        })
        return

    # Set status: running
    now = datetime.now(timezone.utc)
    await db.execute(
        update(Execution)
        .where(Execution.id == execution_id)
        .values(status="running", started_at=now)
    )
    await db.commit()

    _log_execution_event(
        logging.INFO,
        "execution_running",
        execution_id=exec_id_str,
        workflow_id=str(workflow_id),
        tenant_id=str(tenant_id),
    )

    # Initialize state
    state = AgentState({
        "messages": [],
        "current_agent": "",
        "results": {},
        "metadata": {
            "execution_id": str(execution_id),
            "tenant_id": str(tenant_id),
            "workflow_id": str(workflow_id),
        },
    })

    # Add input data to messages
    if input_data:
        input_text = input_data.get("text", "") or input_data.get("message", "") or json.dumps(input_data)
        state["messages"].append({"role": "user", "content": input_text})

    # Execute graph step by step
    # Instead of using graph.ainvoke (which runs everything in one shot),
    # we iterate node by node to intercept each step for logging/WS/budget
    nodes = definition.get("nodes", [])
    edges = definition.get("edges", [])

    # Build execution order via topological sort
    execution_order = _topological_sort(nodes, edges)

    step_number = 0
    iteration = 0

    for node_id in execution_order:
        iteration += 1
        if iteration > MAX_ITERATIONS:
            await _fail_execution(db, execution_id, "Max iterations exceeded")
            await _broadcast_ws(exec_id_str, {
                "type": "error",
                "data": {"message": "Max iterations exceeded", "agent_name": node_id, "step_number": step_number},
            })
            return

        # Check cancellation
        if _is_cancelled(exec_id_str):
            await _cancel_execution(db, execution_id)
            await _broadcast_ws(exec_id_str, {
                "type": "execution_complete",
                "data": {"status": "cancelled", "total_tokens": 0, "total_cost": 0.0},
            })
            return

        agent_config = agent_config_map.get(node_id)
        if not agent_config:
            _log_execution_event(
                logging.WARNING,
                "execution_node_missing_agent_config",
                execution_id=exec_id_str,
                workflow_id=str(workflow_id),
                tenant_id=str(tenant_id),
                node_id=node_id,
            )
            continue

        step_number += 1
        state["current_agent"] = agent_config.name

        # Broadcast step_start
        await _broadcast_ws(exec_id_str, {
            "type": "step_start",
            "data": {"agent_name": agent_config.name, "step_number": step_number},
        })

        _log_execution_event(
            logging.INFO,
            "execution_step_started",
            execution_id=exec_id_str,
            workflow_id=str(workflow_id),
            tenant_id=str(tenant_id),
            step_number=step_number,
            agent_name=agent_config.name,
        )

        # Check budget before LLM call
        tenant_result = await db.execute(select(Tenant).where(Tenant.id == tenant_id))
        tenant = tenant_result.scalar_one_or_none()
        if tenant and tenant.tokens_used_this_month >= tenant.monthly_token_budget:
            error_msg = "Monthly token budget exceeded"
            await _cancel_execution(db, execution_id, error_msg)
            await _broadcast_ws(exec_id_str, {
                "type": "error",
                "data": {"message": error_msg, "agent_name": agent_config.name, "step_number": step_number},
            })
            return

        # Execute agent
        agent_result = await execute_agent(agent_config, state, db, tenant_id)

        # Record execution log
        log = ExecutionLog(
            execution_id=execution_id,
            agent_config_id=agent_config.id,
            step_number=step_number,
            agent_name=agent_config.name,
            action=agent_result["action"],
            input_data={"messages": state.get("messages", [])[-1:]} if state.get("messages") else None,
            output_data={"content": agent_result["output"]},
            tokens_used=agent_result["input_tokens"] + agent_result["output_tokens"],
            cost=agent_result["cost"],
            decision_reasoning=agent_result.get("reasoning"),
            duration_ms=agent_result["duration_ms"],
        )
        db.add(log)

        # Update execution totals
        total_tokens = agent_result["input_tokens"] + agent_result["output_tokens"]
        await db.execute(
            update(Execution)
            .where(Execution.id == execution_id)
            .values(
                total_tokens=Execution.total_tokens + total_tokens,
                total_cost=Execution.total_cost + agent_result["cost"],
            )
        )

        # Update tenant tokens used
        await db.execute(
            update(Tenant)
            .where(Tenant.id == tenant_id)
            .values(tokens_used_this_month=Tenant.tokens_used_this_month + total_tokens)
        )

        await db.commit()

        # Update state with agent result
        state["results"][agent_config.name] = agent_result["output"]
        state["messages"].append({
            "role": "assistant",
            "content": agent_result["output"],
        })

        # Broadcast step_complete
        await _broadcast_ws(exec_id_str, {
            "type": "step_complete",
            "data": {
                "agent_name": agent_config.name,
                "step_number": step_number,
                "tokens": total_tokens,
                "cost": agent_result["cost"],
                "duration_ms": agent_result["duration_ms"],
            },
        })

        _log_execution_event(
            logging.INFO,
            "execution_step_completed",
            execution_id=exec_id_str,
            workflow_id=str(workflow_id),
            tenant_id=str(tenant_id),
            step_number=step_number,
            agent_name=agent_config.name,
            duration_ms=agent_result["duration_ms"],
            total_tokens=total_tokens,
            total_cost=agent_result["cost"],
        )

    # Execution complete
    now = datetime.now(timezone.utc)

    # Get final totals
    exec_result = await db.execute(
        select(Execution).where(Execution.id == execution_id)
    )
    execution = exec_result.scalar_one_or_none()

    output_data = state.get("results", {})

    await db.execute(
        update(Execution)
        .where(Execution.id == execution_id)
        .values(
            status="completed",
            output_data=output_data,
            completed_at=now,
        )
    )
    await db.commit()

    _log_execution_event(
        logging.INFO,
        "execution_completed",
        execution_id=exec_id_str,
        workflow_id=str(workflow_id),
        tenant_id=str(tenant_id),
        total_tokens=execution.total_tokens if execution else 0,
        total_cost=execution.total_cost if execution else 0.0,
    )

    # Broadcast execution_complete
    await _broadcast_ws(exec_id_str, {
        "type": "execution_complete",
        "data": {
            "status": "completed",
            "total_tokens": execution.total_tokens if execution else 0,
            "total_cost": execution.total_cost if execution else 0.0,
            "output_data": output_data,
        },
    })


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _topological_sort(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Topological sort of nodes based on edges.

    Returns list of node IDs in execution order.
    Falls back to definition order if graph has cycles.
    """
    node_ids = [n.get("id") for n in nodes]
    adj: dict[str, list[str]] = {nid: [] for nid in node_ids}
    in_degree: dict[str, int] = {nid: 0 for nid in node_ids}

    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if source in adj and target in in_degree:
            adj[source].append(target)
            in_degree[target] += 1

    # Kahn's algorithm
    queue = [nid for nid in node_ids if in_degree[nid] == 0]
    result = []

    while queue:
        node = queue.pop(0)
        result.append(node)
        for neighbor in adj.get(node, []):
            in_degree[neighbor] -= 1
            if in_degree[neighbor] == 0:
                queue.append(neighbor)

    # If not all nodes processed — cyclic graph, append remaining in definition order
    if len(result) < len(node_ids):
        remaining = [nid for nid in node_ids if nid not in result]
        result.extend(remaining)

    return result


async def _fail_execution(db: AsyncSession, execution_id: UUID, error_message: str) -> None:
    """Mark execution as failed."""
    now = datetime.now(timezone.utc)
    await db.execute(
        update(Execution)
        .where(Execution.id == execution_id)
        .values(
            status="failed",
            error_message=error_message,
            completed_at=now,
        )
    )
    await db.commit()
    _log_execution_event(
        logging.ERROR,
        "execution_failed",
        execution_id=str(execution_id),
        error=error_message,
    )


async def _cancel_execution(
    db: AsyncSession, execution_id: UUID, error_message: str = "Execution cancelled by user"
) -> None:
    """Mark execution as cancelled."""
    now = datetime.now(timezone.utc)
    await db.execute(
        update(Execution)
        .where(Execution.id == execution_id)
        .values(
            status="cancelled",
            error_message=error_message,
            completed_at=now,
        )
    )
    await db.commit()
    _log_execution_event(
        logging.INFO,
        "execution_cancelled",
        execution_id=str(execution_id),
        error=error_message,
    )
