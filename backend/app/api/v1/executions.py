"""
Execution API routes.

Endpoints:
    POST   /api/v1/workflows/{wf_id}/execute  — start execution
    GET    /api/v1/executions                  — list executions (paginated)
    GET    /api/v1/executions/{id}             — get execution details
    GET    /api/v1/executions/{id}/logs        — get execution step logs
    POST   /api/v1/executions/{id}/cancel      — cancel running execution
    WS     /api/v1/executions/{id}/stream      — WebSocket live events
"""

import asyncio
import base64
import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status, BackgroundTasks, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_tenant, require_role
from app.core.security import decode_token
from app.models.execution import Execution
from app.models.user import User
from app.schemas.execution import (
    ExecutionCreate,
    ExecutionStartResponse,
    ExecutionResponse,
    ExecutionListResponse,
    ExecutionLogResponse,
)
from app.services import execution_service
from app.engine.executor import run_execution, subscribe_ws, unsubscribe_ws

router = APIRouter(tags=["executions"])


# ---------------------------------------------------------------------------
# POST /workflows/{wf_id}/execute — start execution
# ---------------------------------------------------------------------------

@router.post(
    "/workflows/{wf_id}/execute",
    response_model=ExecutionStartResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_execution(
    wf_id: UUID,
    body: ExecutionCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role("owner", "editor")),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """Start a workflow execution. Returns immediately with execution_id.

    The actual execution runs in a background task.
    """
    execution = await execution_service.create_execution(
        db=db,
        tenant_id=tenant_id,
        workflow_id=wf_id,
        input_data=body.input_data,
    )

    # Launch execution in background
    # We need a fresh DB session for the background task
    from app.core.database import async_session_factory

    async def _run_in_background():
        async with async_session_factory() as bg_db:
            try:
                await run_execution(
                    execution_id=execution.id,
                    workflow_id=wf_id,
                    tenant_id=tenant_id,
                    input_data=body.input_data,
                    db=bg_db,
                )
            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Background execution error: {e}")

    background_tasks.add_task(_run_in_background)

    return ExecutionStartResponse(
        execution_id=execution.id,
        status=execution.status,
    )


# ---------------------------------------------------------------------------
# GET /executions — list executions
# ---------------------------------------------------------------------------

@router.get("/executions", response_model=ExecutionListResponse)
async def list_executions(
    workflow_id: UUID | None = None,
    status_filter: str | None = None,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """List executions for the current tenant. Supports filtering by workflow_id and status."""
    result = await execution_service.list_executions(
        db=db,
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        status_filter=status_filter,
        page=page,
        per_page=per_page,
    )
    return ExecutionListResponse(
        items=[ExecutionResponse.model_validate(e) for e in result["items"]],
        total=result["total"],
        page=result["page"],
        per_page=result["per_page"],
    )


# ---------------------------------------------------------------------------
# GET /executions/{id} — get execution details
# ---------------------------------------------------------------------------

@router.get("/executions/{execution_id}", response_model=ExecutionResponse)
async def get_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """Get a single execution by ID."""
    execution = await execution_service.get_execution(db, tenant_id, execution_id)
    return ExecutionResponse.model_validate(execution)


# ---------------------------------------------------------------------------
# GET /executions/{id}/logs — get execution step logs
# ---------------------------------------------------------------------------

@router.get("/executions/{execution_id}/logs", response_model=list[ExecutionLogResponse])
async def get_execution_logs(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """Get all step logs for an execution."""
    logs = await execution_service.get_execution_logs(db, tenant_id, execution_id)
    return [ExecutionLogResponse.model_validate(log) for log in logs]


# ---------------------------------------------------------------------------
# POST /executions/{id}/cancel — cancel execution
# ---------------------------------------------------------------------------

@router.post("/executions/{execution_id}/cancel", response_model=ExecutionResponse)
async def cancel_execution(
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    tenant_id: UUID = Depends(get_current_tenant),
):
    """Cancel a running or pending execution."""
    execution = await execution_service.cancel_execution(db, tenant_id, execution_id)
    return ExecutionResponse.model_validate(execution)


# ---------------------------------------------------------------------------
# WS /executions/{id}/stream — WebSocket live events
# ---------------------------------------------------------------------------

@router.websocket("/executions/{execution_id}/stream")
async def execution_stream(
    websocket: WebSocket,
    execution_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """WebSocket endpoint for streaming execution events in real-time.

    Events sent to client:
    - step_start: {agent_name, step_number}
    - step_complete: {agent_name, step_number, tokens, cost, duration_ms}
    - execution_complete: {status, total_tokens, total_cost, output_data}
    - error: {message, agent_name, step_number}
    """
    token = None
    subprotocol = None
    protocol_header = websocket.headers.get("sec-websocket-protocol", "")
    protocols = [p.strip() for p in protocol_header.split(",") if p.strip()]

    if "graphpilot.v1" in protocols:
        subprotocol = "graphpilot.v1"

    auth_header = websocket.headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

    if not token:
        bearer_protocol = next((p for p in protocols if p.startswith("bearer.")), None)
        if bearer_protocol:
            encoded = bearer_protocol[len("bearer."):]
            padding = "=" * (-len(encoded) % 4)
            try:
                token = base64.urlsafe_b64decode(f"{encoded}{padding}").decode("utf-8")
            except Exception:
                token = None

    payload = decode_token(token) if token else None
    if payload is None or payload.get("type") != "access":
        await websocket.close(code=1008, reason="Unauthorized")
        return

    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=1008, reason="Unauthorized")
        return

    try:
        user_uuid = UUID(user_id)
    except ValueError:
        await websocket.close(code=1008, reason="Unauthorized")
        return

    user_result = await db.execute(select(User).where(User.id == user_uuid))
    user = user_result.scalar_one_or_none()
    if user is None or not user.is_active:
        await websocket.close(code=1008, reason="Unauthorized")
        return

    exec_result = await db.execute(
        select(Execution).where(
            Execution.id == execution_id,
            Execution.tenant_id == user.tenant_id,
        )
    )
    execution = exec_result.scalar_one_or_none()
    if execution is None:
        await websocket.close(code=1008, reason="Execution not found")
        return

    if subprotocol:
        await websocket.accept(subprotocol=subprotocol)
    else:
        await websocket.accept()

    exec_id_str = str(execution_id)
    queue = subscribe_ws(exec_id_str)

    try:
        while True:
            try:
                # Wait for events with timeout to check for disconnects
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(event)

                # If execution_complete or error with no step, we can close
                if event.get("type") == "execution_complete":
                    break
            except asyncio.TimeoutError:
                # Send ping to keep connection alive
                try:
                    await websocket.send_json({"type": "ping", "data": {}})
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        unsubscribe_ws(exec_id_str, queue)
