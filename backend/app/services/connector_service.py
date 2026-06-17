import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.connector import ConnectorCredential, WebhookEvent, WorkflowTrigger
from app.models.workflow import Workflow
from app.models.execution import Execution
from app.services.analytics_service import invalidate_tenant_cache
from app.services.connector_security import (
    build_config_preview,
    encrypt_config,
    redact_secret_values,
)


HTTP_CONNECTOR_MANIFEST = {
    "key": "http",
    "name": "HTTP",
    "description": "Make HTTP requests with explicit network safety and redacted logs.",
    "version": "1.0.0",
    "auth_types": ["none", "api_key_header"],
    "actions": [
        {
            "key": "request",
            "name": "Request",
            "input_schema": {
                "type": "object",
                "required": ["url", "method"],
                "properties": {
                    "url": {"type": "string", "format": "uri"},
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"],
                    },
                    "headers": {"type": "object"},
                    "query": {"type": "object"},
                    "body": {},
                },
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "status_code": {"type": "integer"},
                    "headers": {"type": "object"},
                    "body": {},
                },
            },
            "retry": {
                "max_attempts": 1,
                "retryable_statuses": [408, 429, 500, 502, 503, 504],
            },
        }
    ],
}

BUILT_IN_CONNECTORS = {HTTP_CONNECTOR_MANIFEST["key"]: HTTP_CONNECTOR_MANIFEST}


def _connector_summary(manifest: dict) -> dict:
    return {
        "key": manifest["key"],
        "name": manifest["name"],
        "description": manifest.get("description", ""),
        "version": manifest.get("version", "1.0.0"),
        "auth_types": manifest.get("auth_types", []),
        "actions": [
            {"key": action["key"], "name": action["name"]}
            for action in manifest.get("actions", [])
        ],
    }


def list_connectors() -> list[dict]:
    return [_connector_summary(manifest) for manifest in BUILT_IN_CONNECTORS.values()]


def get_connector(connector_key: str) -> dict:
    manifest = BUILT_IN_CONNECTORS.get(connector_key)
    if manifest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found",
        )
    return {
        "key": manifest["key"],
        "name": manifest["name"],
        "description": manifest.get("description", ""),
        "version": manifest.get("version", "1.0.0"),
        "manifest": manifest,
    }


def _validate_connector_auth(connector_key: str, auth_type: str, config: dict) -> None:
    manifest = BUILT_IN_CONNECTORS.get(connector_key)
    if manifest is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector not found",
        )
    if auth_type not in manifest.get("auth_types", []):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Auth type '{auth_type}' is not supported by connector '{connector_key}'.",
        )
    if auth_type == "api_key_header":
        if not config.get("header_name") or not config.get("header_value"):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="API key header credentials require header_name and header_value.",
            )


async def create_credential(
    db: AsyncSession,
    tenant_id: UUID,
    user_id: UUID,
    connector_key: str,
    name: str,
    auth_type: str,
    config: dict,
) -> ConnectorCredential:
    _validate_connector_auth(connector_key, auth_type, config)

    credential = ConnectorCredential(
        tenant_id=tenant_id,
        connector_key=connector_key,
        name=name,
        auth_type=auth_type,
        encrypted_config=encrypt_config(config),
        config_preview=build_config_preview(auth_type, config),
        created_by=user_id,
    )
    db.add(credential)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Connector credential with name '{name}' already exists.",
        ) from exc
    await db.refresh(credential)
    return credential


async def list_credentials(
    db: AsyncSession,
    tenant_id: UUID,
    connector_key: str | None = None,
) -> list[ConnectorCredential]:
    query = select(ConnectorCredential).where(
        ConnectorCredential.tenant_id == tenant_id,
        ConnectorCredential.is_active == True,  # noqa: E712
    )
    if connector_key:
        query = query.where(ConnectorCredential.connector_key == connector_key)
    result = await db.execute(query.order_by(ConnectorCredential.created_at))
    return list(result.scalars().all())


async def get_credential(
    db: AsyncSession,
    tenant_id: UUID,
    credential_id: UUID,
) -> ConnectorCredential:
    result = await db.execute(
        select(ConnectorCredential).where(
            ConnectorCredential.id == credential_id,
            ConnectorCredential.tenant_id == tenant_id,
            ConnectorCredential.is_active == True,  # noqa: E712
        )
    )
    credential = result.scalar_one_or_none()
    if credential is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connector credential not found",
        )
    return credential


async def delete_credential(
    db: AsyncSession,
    tenant_id: UUID,
    credential_id: UUID,
) -> None:
    credential = await get_credential(db, tenant_id, credential_id)
    credential.is_active = False
    await db.commit()


async def _get_workflow(db: AsyncSession, tenant_id: UUID, workflow_id: UUID) -> Workflow:
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


def _get_trigger_rate_limit(config: dict | None) -> tuple[int, int] | None:
    rate_limit = (config or {}).get("rate_limit")
    if not isinstance(rate_limit, dict) or rate_limit.get("enabled") is not True:
        return None

    try:
        max_events = int(rate_limit.get("max_events"))
        window_seconds = int(rate_limit.get("window_seconds"))
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Webhook trigger rate_limit requires positive max_events and window_seconds.",
        ) from exc

    if max_events < 1 or window_seconds < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Webhook trigger rate_limit requires positive max_events and window_seconds.",
        )

    return max_events, window_seconds


_SUPPORTED_WEBHOOK_AUTH = {"none", "hmac"}
_ALLOWED_HMAC_ALGORITHMS = {"sha256", "sha1", "sha512"}


def _webhook_auth_type(config: dict | None) -> str:
    auth = (config or {}).get("auth")
    if isinstance(auth, dict):
        return str(auth.get("type") or "none").lower()
    if isinstance(auth, str):
        return auth.lower()
    return "none"


def _hmac_settings(config: dict | None) -> dict:
    auth = (config or {}).get("auth")
    if isinstance(auth, dict):
        return auth
    settings = (config or {}).get("hmac")
    return settings if isinstance(settings, dict) else {}


def _validate_webhook_auth_config(config: dict | None) -> None:
    auth_type = _webhook_auth_type(config)
    if auth_type not in _SUPPORTED_WEBHOOK_AUTH:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Webhook trigger auth must be one of: none, hmac.",
        )
    if auth_type != "hmac":
        return
    hmac_cfg = _hmac_settings(config)
    secret = hmac_cfg.get("secret")
    if not isinstance(secret, str) or len(secret) < 16:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="HMAC webhook auth requires a secret of at least 16 characters.",
        )
    algorithm = str(hmac_cfg.get("algorithm", "sha256")).lower()
    if algorithm not in _ALLOWED_HMAC_ALGORITHMS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="HMAC webhook auth algorithm must be one of: sha256, sha1, sha512.",
        )
    tolerance = hmac_cfg.get("tolerance_seconds")
    if tolerance is not None:
        try:
            if int(tolerance) < 0:
                raise ValueError
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="HMAC webhook tolerance_seconds must be a non-negative integer.",
            ) from exc


def _verify_webhook_signature(
    config: dict | None,
    raw_body: bytes,
    headers: dict,
) -> None:
    """Verify webhook authenticity for triggers configured with HMAC auth.

    Backward compatible: triggers with auth "none" (or unset) are not verified.
    Header lookups are case-insensitive (Starlette lowercases header keys).
    """
    if _webhook_auth_type(config) != "hmac":
        return

    lowered = {str(k).lower(): str(v) for k, v in (headers or {}).items()}
    hmac_cfg = _hmac_settings(config)
    secret = str(hmac_cfg.get("secret") or "")
    if not secret:
        # Misconfigured trigger — fail closed rather than accept unsigned calls.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook signature verification is misconfigured.",
        )
    algorithm = str(hmac_cfg.get("algorithm", "sha256")).lower()
    if algorithm not in _ALLOWED_HMAC_ALGORITHMS:
        algorithm = "sha256"
    signature_header = str(hmac_cfg.get("signature_header", "X-Signature-256")).lower()
    timestamp_header = hmac_cfg.get("timestamp_header")
    tolerance = hmac_cfg.get("tolerance_seconds")

    provided = lowered.get(signature_header, "")
    if "=" in provided:
        provided = provided.split("=", 1)[1]
    if not provided:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook signature is missing.",
        )

    signed_payload = raw_body
    if timestamp_header:
        timestamp_value = lowered.get(str(timestamp_header).lower(), "")
        if not timestamp_value:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Webhook timestamp is missing.",
            )
        try:
            ts = int(timestamp_value)
        except (TypeError, ValueError) as exc:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Webhook timestamp is invalid.",
            ) from exc
        if tolerance is not None and abs(int(time.time()) - ts) > int(tolerance):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Webhook timestamp is outside the allowed window.",
            )
        signed_payload = f"{timestamp_value}.".encode("utf-8") + raw_body

    expected = hmac.new(secret.encode("utf-8"), signed_payload, algorithm).hexdigest()
    if not hmac.compare_digest(expected, provided.strip()):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Webhook signature is invalid.",
        )


async def _enforce_webhook_rate_limit(db: AsyncSession, trigger: WorkflowTrigger) -> None:
    rate_limit = _get_trigger_rate_limit(trigger.config)
    if rate_limit is None:
        return

    max_events, window_seconds = rate_limit
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    result = await db.execute(
        select(func.count(WebhookEvent.id)).where(
            WebhookEvent.tenant_id == trigger.tenant_id,
            WebhookEvent.trigger_id == trigger.id,
            WebhookEvent.created_at >= cutoff,
        )
    )
    accepted_events = result.scalar_one()
    if accepted_events >= max_events:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Webhook trigger rate limit exceeded.",
        )


async def create_trigger(
    db: AsyncSession,
    tenant_id: UUID,
    workflow_id: UUID,
    user_id: UUID,
    trigger_type: str,
    config: dict,
) -> WorkflowTrigger:
    await _get_workflow(db, tenant_id, workflow_id)
    if trigger_type != "webhook":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="M9 supports only webhook triggers.",
        )
    _get_trigger_rate_limit(config)
    _validate_webhook_auth_config(config)

    trigger = WorkflowTrigger(
        tenant_id=tenant_id,
        workflow_id=workflow_id,
        trigger_type=trigger_type,
        public_id=secrets.token_urlsafe(32),
        config=config,
        created_by=user_id,
    )
    db.add(trigger)
    await db.commit()
    await db.refresh(trigger)
    return trigger


async def list_triggers(
    db: AsyncSession,
    tenant_id: UUID,
    workflow_id: UUID,
) -> list[WorkflowTrigger]:
    await _get_workflow(db, tenant_id, workflow_id)
    result = await db.execute(
        select(WorkflowTrigger)
        .where(
            WorkflowTrigger.tenant_id == tenant_id,
            WorkflowTrigger.workflow_id == workflow_id,
            WorkflowTrigger.is_active == True,  # noqa: E712
        )
        .order_by(WorkflowTrigger.created_at)
    )
    return list(result.scalars().all())


async def ingest_webhook(
    db: AsyncSession,
    public_trigger_id: str,
    payload: dict,
    headers: dict,
    raw_body: bytes = b"",
) -> SimpleNamespace:
    result = await db.execute(
        select(WorkflowTrigger).where(
            WorkflowTrigger.public_id == public_trigger_id,
            WorkflowTrigger.trigger_type == "webhook",
            WorkflowTrigger.is_active == True,  # noqa: E712
        )
    )
    trigger = result.scalar_one_or_none()
    if trigger is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Webhook not found")

    # Authenticity check happens before any billable work (execution creation).
    _verify_webhook_signature(trigger.config, raw_body, headers)

    workflow = await _get_workflow(db, trigger.tenant_id, trigger.workflow_id)
    await _enforce_webhook_rate_limit(db, trigger)

    # Admission control: bound queue backlog and reject when budget is exhausted.
    # Holds a tenant-row lock until the commit below so concurrent ingests cannot
    # both slip past the backlog cap.
    from app.services.execution_service import enforce_webhook_admission

    await enforce_webhook_admission(db, trigger.tenant_id)
    event = WebhookEvent(
        tenant_id=trigger.tenant_id,
        workflow_id=trigger.workflow_id,
        trigger_id=trigger.id,
        payload=payload,
        headers_sanitized=redact_secret_values(headers),
        status="received",
    )
    db.add(event)
    await db.flush()

    execution = Execution(
        tenant_id=trigger.tenant_id,
        workflow_id=workflow.id,
        status="pending",
        input_data={
            "trigger": {
                "type": "webhook",
                "trigger_id": str(trigger.id),
                "event_id": str(event.id),
            },
            "payload": payload,
            "headers": event.headers_sanitized,
        },
    )
    db.add(execution)
    await db.flush()
    event.execution_id = execution.id
    event.status = "execution_created"
    await db.commit()
    invalidate_tenant_cache(trigger.tenant_id)
    return SimpleNamespace(execution_id=execution.id, status=execution.status)
