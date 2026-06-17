import json
import re
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.compiler import CompilationError, validate_definition
from app.models.agent_config import AgentConfig
from app.models.execution import Execution, ExecutionLog
from app.models.tool_registry import ToolRegistry
from app.models.workflow import Workflow
from app.models.workflow_doctor import WorkflowFixSuggestion, WorkflowReplayRun
from app.schemas.agent_config import VALID_MODELS
from app.schemas.workflow_doctor import VALID_REPLAY_MODES
from app.services.analytics_service import invalidate_tenant_cache


DIAGNOSABLE_EXECUTION_STATUSES = {"failed", "cancelled"}
DEFAULT_SAFE_MODEL = "gpt-4o-mini"
PATCHABLE_STATUSES = {"proposed", "replay_passed", "replay_failed"}
SECRET_PATH_PARTS = {
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "api_key",
    "apikey",
    "access_key",
    "private_key",
}
ALLOWED_PATCH_TARGETS = {
    ("agent_config", "/model"),
    ("tool", "/config/url"),
    ("tool", "/config/method"),
}


async def diagnose_execution(
    db: AsyncSession,
    tenant_id: UUID,
    execution_id: UUID,
    force: bool = False,
) -> list[WorkflowFixSuggestion]:
    execution = await _get_execution(db, tenant_id, execution_id)
    if execution.status not in DIAGNOSABLE_EXECUTION_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Cannot diagnose execution with status '{execution.status}'. "
                "Only failed or cancelled executions can be diagnosed."
            ),
        )

    existing = await _list_suggestions_for_execution(db, tenant_id, execution_id)
    if existing and not force:
        return existing

    if force and existing:
        now = _utcnow()
        for suggestion in existing:
            if suggestion.status in PATCHABLE_STATUSES:
                suggestion.status = "dismissed"
                suggestion.dismissed_at = now

    logs = await _get_execution_logs(db, execution_id)
    workflow = await _get_workflow(db, tenant_id, execution.workflow_id)
    error_text = _collect_error_text(execution, logs)
    suggestion = await _build_suggestion(db, tenant_id, execution, workflow, logs, error_text)

    db.add(suggestion)
    await db.commit()
    await db.refresh(suggestion)
    return [suggestion]


async def list_suggestions(
    db: AsyncSession,
    tenant_id: UUID,
    execution_id: UUID,
) -> list[WorkflowFixSuggestion]:
    await _get_execution(db, tenant_id, execution_id)
    return await _list_suggestions_for_execution(db, tenant_id, execution_id)


async def replay_suggestion(
    db: AsyncSession,
    tenant_id: UUID,
    suggestion_id: UUID,
    mode: str = "validation_only",
) -> WorkflowReplayRun:
    if mode not in VALID_REPLAY_MODES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid replay mode. Must be one of: {', '.join(sorted(VALID_REPLAY_MODES))}",
        )

    suggestion = await _get_suggestion(db, tenant_id, suggestion_id)
    if suggestion.status in {"applied", "dismissed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot replay a suggestion with status '{suggestion.status}'.",
        )

    replay_run = WorkflowReplayRun(
        tenant_id=tenant_id,
        workflow_id=suggestion.workflow_id,
        execution_id=suggestion.execution_id,
        suggestion_id=suggestion.id,
        mode=mode,
        status="running",
        result={"external_calls_executed": False},
    )
    db.add(replay_run)
    await db.flush()

    try:
        _validate_patch_operations(suggestion.patch)
        result = await _validate_replay_patch(db, tenant_id, suggestion)
        replay_run.status = "passed"
        replay_run.result = result
        suggestion.status = "replay_passed"
        suggestion.replay_result = result
    except HTTPException as exc:
        replay_run.status = "failed"
        replay_run.result = {
            "external_calls_executed": False,
            "error": str(exc.detail),
        }
        suggestion.status = "replay_failed"
        suggestion.replay_result = replay_run.result
    except Exception as exc:
        replay_run.status = "failed"
        replay_run.result = {
            "external_calls_executed": False,
            "error": str(exc),
        }
        suggestion.status = "replay_failed"
        suggestion.replay_result = replay_run.result

    replay_run.completed_at = _utcnow()
    await db.commit()
    await db.refresh(replay_run)
    return replay_run


async def apply_suggestion(
    db: AsyncSession,
    tenant_id: UUID,
    suggestion_id: UUID,
    user_id: UUID,
    retry: bool = True,
) -> dict[str, UUID | str | None]:
    suggestion = await _get_suggestion(db, tenant_id, suggestion_id)
    if suggestion.status in {"applied", "dismissed"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Cannot apply a suggestion with status '{suggestion.status}'.",
        )

    _validate_patch_operations(suggestion.patch)
    await _apply_patch_operations(db, tenant_id, suggestion.patch)

    retry_execution_id: UUID | None = None
    if retry:
        original_execution = await _get_execution(db, tenant_id, suggestion.execution_id)
        retry_execution = Execution(
            tenant_id=tenant_id,
            workflow_id=suggestion.workflow_id,
            status="pending",
            input_data=original_execution.input_data,
        )
        db.add(retry_execution)
        await db.flush()
        retry_execution_id = retry_execution.id
        invalidate_tenant_cache(tenant_id)

    suggestion.status = "applied"
    suggestion.applied_by = user_id
    suggestion.applied_at = _utcnow()
    await db.commit()
    return {
        "suggestion_id": suggestion.id,
        "status": suggestion.status,
        "retry_execution_id": retry_execution_id,
    }


async def dismiss_suggestion(
    db: AsyncSession,
    tenant_id: UUID,
    suggestion_id: UUID,
) -> dict[str, UUID | str]:
    suggestion = await _get_suggestion(db, tenant_id, suggestion_id)
    if suggestion.status == "applied":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Applied suggestions cannot be dismissed.",
        )

    suggestion.status = "dismissed"
    suggestion.dismissed_at = _utcnow()
    await db.commit()
    return {"suggestion_id": suggestion.id, "status": suggestion.status}


async def _build_suggestion(
    db: AsyncSession,
    tenant_id: UUID,
    execution: Execution,
    workflow: Workflow,
    logs: list[ExecutionLog],
    error_text: str,
) -> WorkflowFixSuggestion:
    lowered = error_text.lower()

    if "api_key not configured" in lowered:
        provider = "OpenAI" if "openai" in lowered else "Anthropic"
        return WorkflowFixSuggestion(
            tenant_id=tenant_id,
            workflow_id=workflow.id,
            execution_id=execution.id,
            agent_config_id=_first_agent_config_id(logs),
            detector_code="missing_provider_key",
            title=f"{provider} provider key is not configured",
            root_cause=(
                f"The execution failed before model invocation because the {provider} "
                "provider key is missing from the server environment."
            ),
            recommendation=(
                "Configure the provider API key in the backend environment and restart "
                "the worker before retrying this execution."
            ),
            severity="high",
            confidence=0.95,
            patch={"operations": []},
        )

    if "agent configs missing" in lowered:
        return WorkflowFixSuggestion(
            tenant_id=tenant_id,
            workflow_id=workflow.id,
            execution_id=execution.id,
            detector_code="missing_agent_config",
            title="Workflow node is missing an agent config",
            root_cause=_trim_public_error(error_text),
            recommendation=(
                "Open the workflow builder, configure agents for every node, then run "
                "the execution again."
            ),
            severity="critical",
            confidence=0.9,
            patch={"operations": []},
        )

    if "missing_connector_credential" in lowered or (
        "connector credential" in lowered and "missing" in lowered
    ):
        return WorkflowFixSuggestion(
            tenant_id=tenant_id,
            workflow_id=workflow.id,
            execution_id=execution.id,
            agent_config_id=None,
            detector_code="missing_connector_credential",
            title="Connector credential is missing or inactive",
            root_cause=_trim_public_error(error_text),
            recommendation=(
                "Create or re-enable the connector credential, attach it to the "
                "connector node, then retry the execution."
            ),
            severity="high",
            confidence=0.9,
            patch={"operations": []},
        )

    if "unsupported model" in lowered or await _workflow_has_unsupported_model(
        db, tenant_id, workflow.id
    ):
        agent = await _find_agent_for_suggestion(db, tenant_id, workflow.id, logs)
        model = _extract_unsupported_model(error_text) or (agent.model if agent else "unknown")
        patch = {"operations": []}
        agent_id = None
        if agent is not None:
            agent_id = agent.id
            patch = {
                "operations": [
                    {
                        "op": "replace",
                        "target_type": "agent_config",
                        "target_id": str(agent.id),
                        "path": "/model",
                        "value": DEFAULT_SAFE_MODEL,
                        "current_value": model,
                    }
                ]
            }
        return WorkflowFixSuggestion(
            tenant_id=tenant_id,
            workflow_id=workflow.id,
            execution_id=execution.id,
            agent_config_id=agent_id,
            detector_code="unsupported_model",
            title="Agent model is not supported by this workspace",
            root_cause=f"Agent execution referenced unsupported model '{model}'.",
            recommendation=(
                f"Replace the model with '{DEFAULT_SAFE_MODEL}', validate the workflow "
                "without external calls, then retry."
            ),
            severity="high",
            confidence=0.9 if agent is not None else 0.65,
            patch=patch,
        )

    return WorkflowFixSuggestion(
        tenant_id=tenant_id,
        workflow_id=workflow.id,
        execution_id=execution.id,
        agent_config_id=_first_agent_config_id(logs),
        detector_code="no_diagnosis_available",
        title="No known fix pattern matched this failure",
        root_cause=_trim_public_error(error_text) or "The execution failed without a recognized error pattern.",
        recommendation="Review the execution logs and adjust the workflow manually.",
        severity="medium",
        confidence=0.2,
        patch={"operations": []},
    )


async def _validate_replay_patch(
    db: AsyncSession,
    tenant_id: UUID,
    suggestion: WorkflowFixSuggestion,
) -> dict[str, Any]:
    workflow = await _get_workflow(db, tenant_id, suggestion.workflow_id)
    agents_result = await db.execute(
        select(AgentConfig).where(
            AgentConfig.tenant_id == tenant_id,
            AgentConfig.workflow_id == workflow.id,
        )
    )
    agents = {
        str(agent.id): {
            "id": str(agent.id),
            "node_id": agent.node_id,
            "model": agent.model,
        }
        for agent in agents_result.scalars().all()
    }

    _apply_operations_to_agent_snapshot(agents, suggestion.patch)
    try:
        validate_definition(workflow.definition)
    except CompilationError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Invalid workflow graph after patch: {exc}",
        ) from exc

    node_ids = {
        node.get("id")
        for node in workflow.definition.get("nodes", [])
        if (node.get("type") or "agent") == "agent"
    }
    configured_node_ids = {agent["node_id"] for agent in agents.values()}
    missing_nodes = node_ids - configured_node_ids
    if missing_nodes:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Agent configs still missing for nodes: {sorted(missing_nodes)}",
        )

    unsupported_models = sorted(
        {
            str(agent["model"])
            for agent in agents.values()
            if agent["model"] not in VALID_MODELS
        }
    )
    if unsupported_models:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Unsupported models remain after patch: {unsupported_models}",
        )

    return {
        "external_calls_executed": False,
        "checks": [
            "patch_paths_allowed",
            "workflow_definition_valid",
            "agent_configs_present",
            "agent_models_supported",
        ],
        "message": "Patch validated without executing tools or model calls.",
    }


async def _apply_patch_operations(
    db: AsyncSession,
    tenant_id: UUID,
    patch: dict[str, Any],
) -> None:
    for operation in patch.get("operations", []):
        target_type = operation["target_type"]
        if target_type == "agent_config":
            await _apply_agent_config_operation(db, tenant_id, operation)
        elif target_type == "tool":
            await _apply_tool_operation(db, tenant_id, operation)


async def _apply_agent_config_operation(
    db: AsyncSession,
    tenant_id: UUID,
    operation: dict[str, Any],
) -> None:
    result = await db.execute(
        select(AgentConfig).where(
            AgentConfig.id == UUID(operation["target_id"]),
            AgentConfig.tenant_id == tenant_id,
        )
    )
    agent = result.scalar_one_or_none()
    if agent is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Agent config targeted by patch was not found.",
        )

    if operation["path"] == "/model":
        value = operation["value"]
        if value not in VALID_MODELS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Patch model '{value}' is not supported.",
            )
        agent.model = value


async def _apply_tool_operation(
    db: AsyncSession,
    tenant_id: UUID,
    operation: dict[str, Any],
) -> None:
    result = await db.execute(
        select(ToolRegistry).where(
            ToolRegistry.id == UUID(operation["target_id"]),
            ToolRegistry.tenant_id == tenant_id,
            ToolRegistry.is_active == True,  # noqa: E712
        )
    )
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tool targeted by patch was not found.",
        )

    config = dict(tool.config or {})
    if operation["path"] == "/config/url":
        config["url"] = operation["value"]
    elif operation["path"] == "/config/method":
        config["method"] = operation["value"]
    tool.config = config


def _validate_patch_operations(patch: dict[str, Any] | None) -> None:
    if not isinstance(patch, dict):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Patch must be an object.",
        )

    operations = patch.get("operations", [])
    if not isinstance(operations, list):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Patch operations must be a list.",
        )

    for operation in operations:
        if not isinstance(operation, dict):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Patch operation must be an object.",
            )
        path = operation.get("path")
        target_type = operation.get("target_type")
        if operation.get("secret") or _is_secret_path(path):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Patch path '{path}' is blocked because it may contain secrets.",
            )
        if operation.get("op") != "replace":
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Only replace patch operations are supported.",
            )
        if not isinstance(operation.get("target_id"), str):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Patch operation target_id must be a string UUID.",
            )
        try:
            UUID(operation["target_id"])
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Patch operation target_id must be a valid UUID.",
            ) from exc
        if (target_type, path) not in ALLOWED_PATCH_TARGETS:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Patch target '{target_type}:{path}' is not allowed.",
            )


def _apply_operations_to_agent_snapshot(
    agents: dict[str, dict[str, str]],
    patch: dict[str, Any],
) -> None:
    for operation in patch.get("operations", []):
        if operation["target_type"] != "agent_config":
            continue
        agent = agents.get(operation["target_id"])
        if agent is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Agent config targeted by patch was not found.",
            )
        if operation["path"] == "/model":
            agent["model"] = operation["value"]


async def _get_execution(
    db: AsyncSession,
    tenant_id: UUID,
    execution_id: UUID,
) -> Execution:
    result = await db.execute(
        select(Execution).where(
            Execution.id == execution_id,
            Execution.tenant_id == tenant_id,
        )
    )
    execution = result.scalar_one_or_none()
    if execution is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Execution not found")
    return execution


async def _get_workflow(
    db: AsyncSession,
    tenant_id: UUID,
    workflow_id: UUID,
) -> Workflow:
    result = await db.execute(
        select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.tenant_id == tenant_id,
            Workflow.is_active == True,  # noqa: E712
        )
    )
    workflow = result.scalar_one_or_none()
    if workflow is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Workflow not found")
    return workflow


async def _get_suggestion(
    db: AsyncSession,
    tenant_id: UUID,
    suggestion_id: UUID,
) -> WorkflowFixSuggestion:
    result = await db.execute(
        select(WorkflowFixSuggestion).where(
            WorkflowFixSuggestion.id == suggestion_id,
            WorkflowFixSuggestion.tenant_id == tenant_id,
        )
    )
    suggestion = result.scalar_one_or_none()
    if suggestion is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Fix suggestion not found",
        )
    return suggestion


async def _list_suggestions_for_execution(
    db: AsyncSession,
    tenant_id: UUID,
    execution_id: UUID,
) -> list[WorkflowFixSuggestion]:
    result = await db.execute(
        select(WorkflowFixSuggestion)
        .where(
            WorkflowFixSuggestion.execution_id == execution_id,
            WorkflowFixSuggestion.tenant_id == tenant_id,
            WorkflowFixSuggestion.status != "dismissed",
        )
        .order_by(desc(WorkflowFixSuggestion.created_at))
    )
    return list(result.scalars().all())


async def _get_execution_logs(
    db: AsyncSession,
    execution_id: UUID,
) -> list[ExecutionLog]:
    result = await db.execute(
        select(ExecutionLog)
        .where(ExecutionLog.execution_id == execution_id)
        .order_by(ExecutionLog.step_number)
    )
    return list(result.scalars().all())


async def _workflow_has_unsupported_model(
    db: AsyncSession,
    tenant_id: UUID,
    workflow_id: UUID,
) -> bool:
    result = await db.execute(
        select(AgentConfig.model).where(
            AgentConfig.tenant_id == tenant_id,
            AgentConfig.workflow_id == workflow_id,
        )
    )
    return any(model not in VALID_MODELS for model in result.scalars().all())


async def _find_agent_for_suggestion(
    db: AsyncSession,
    tenant_id: UUID,
    workflow_id: UUID,
    logs: list[ExecutionLog],
) -> AgentConfig | None:
    agent_id = _first_agent_config_id(logs)
    if agent_id is not None:
        result = await db.execute(
            select(AgentConfig).where(
                AgentConfig.id == agent_id,
                AgentConfig.tenant_id == tenant_id,
            )
        )
        agent = result.scalar_one_or_none()
        if agent is not None:
            return agent

    result = await db.execute(
        select(AgentConfig).where(
            AgentConfig.tenant_id == tenant_id,
            AgentConfig.workflow_id == workflow_id,
            AgentConfig.model.not_in(VALID_MODELS),
        )
    )
    return result.scalar_one_or_none()


def _first_agent_config_id(logs: list[ExecutionLog]) -> UUID | None:
    for log in logs:
        if log.agent_config_id is not None:
            return log.agent_config_id
    return None


def _collect_error_text(execution: Execution, logs: list[ExecutionLog]) -> str:
    pieces = [execution.error_message or ""]
    for log in logs:
        pieces.extend(
            [
                log.agent_name or "",
                log.action or "",
                _public_json(log.input_data),
                _public_json(log.output_data),
                log.decision_reasoning or "",
                log.sanitized_error or "",
            ]
        )
    return "\n".join(piece for piece in pieces if piece)


def _public_json(value: Any) -> str:
    if value is None:
        return ""
    try:
        return json.dumps(value, ensure_ascii=True, default=str)
    except TypeError:
        return str(value)


def _trim_public_error(error_text: str, limit: int = 500) -> str:
    cleaned = " ".join(error_text.split())
    return cleaned[:limit]


def _extract_unsupported_model(error_text: str) -> str | None:
    match = re.search(r"unsupported model:\s*([\w.-]+)", error_text, flags=re.IGNORECASE)
    return match.group(1) if match else None


def _is_secret_path(path: Any) -> bool:
    if not isinstance(path, str):
        return False
    lowered = path.lower()
    return any(part in lowered for part in SECRET_PATH_PARTS)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)
