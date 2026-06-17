import ipaddress
from dataclasses import dataclass
from time import perf_counter
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.tools.safe_http import pinned_http_request, resolve_public_addresses
from app.services.connector_security import (
    decrypt_config,
    redact_secret_values,
    sanitize_error,
)
from app.services.connector_service import BUILT_IN_CONNECTORS, get_credential


class ConnectorRuntimeError(Exception):
    def __init__(
        self,
        message: str,
        *,
        detector_code: str = "connector_runtime_error",
        retryable: bool = False,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.detector_code = detector_code
        self.retryable = retryable
        self.sanitized_error = sanitize_error(message)
        self.input_data = input_data or {}
        self.output_data = output_data or {"error": self.sanitized_error}


@dataclass
class ConnectorResult:
    connector_key: str
    action_key: str
    input_data: dict[str, Any]
    output_data: dict[str, Any]
    duration_ms: int
    retryable: bool = False


def _node_data(node: dict[str, Any]) -> dict[str, Any]:
    data = node.get("data") or {}
    return data if isinstance(data, dict) else {}


def _get_action(connector_key: str, action_key: str) -> dict[str, Any]:
    manifest = BUILT_IN_CONNECTORS.get(connector_key)
    if manifest is None:
        raise ConnectorRuntimeError(
            f"Connector '{connector_key}' is not available.",
            detector_code="connector_not_found",
        )
    for action in manifest.get("actions", []):
        if action.get("key") == action_key:
            return action
    raise ConnectorRuntimeError(
        f"Connector action '{action_key}' is not available for connector '{connector_key}'.",
        detector_code="connector_action_not_found",
    )


def _is_disallowed_ip(value: str) -> bool:
    try:
        ip = ipaddress.ip_address(value)
    except ValueError:
        return True
    return (
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
    )


def assert_public_http_url(url: str) -> None:
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        raise ConnectorRuntimeError("Invalid HTTP connector URL.")
    if (parsed.scheme or "").lower() not in {"http", "https"}:
        raise ConnectorRuntimeError("HTTP connector supports only http or https URLs.")
    if parsed.username or parsed.password:
        raise ConnectorRuntimeError("Credentials in connector URL are not allowed.")
    if host.lower() == "localhost":
        raise ConnectorRuntimeError("HTTP connector URL targets a private or restricted network.")

    try:
        addresses = {str(ipaddress.ip_address(host))}
    except ValueError:
        try:
            addresses = resolve_public_addresses(host, parsed.port)
        except ValueError as exc:
            raise ConnectorRuntimeError(str(exc)) from exc

    if any(_is_disallowed_ip(address) for address in addresses):
        raise ConnectorRuntimeError("HTTP connector URL targets a private or restricted network.")


def _validate_http_input(input_data: dict[str, Any]) -> None:
    if not isinstance(input_data, dict):
        raise ConnectorRuntimeError("Connector input must be an object.")
    url = input_data.get("url")
    if not isinstance(url, str) or not url:
        raise ConnectorRuntimeError("HTTP connector input requires url.")
    method = str(input_data.get("method", "GET")).upper()
    if method not in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
        raise ConnectorRuntimeError("HTTP connector method is not supported.")
    assert_public_http_url(url)


async def execute_connector_node(
    db: AsyncSession,
    tenant_id: UUID,
    node: dict[str, Any],
) -> ConnectorResult:
    data = _node_data(node)
    connector_key = str(data.get("connector_key") or "")
    action_key = str(data.get("action_key") or "")
    action = _get_action(connector_key, action_key)
    input_data = data.get("input") or {}
    if not isinstance(input_data, dict):
        input_data = {}

    credential_config: dict[str, Any] | None = None
    credential_id = data.get("credential_id")
    if credential_id:
        try:
            credential = await get_credential(db, tenant_id, UUID(str(credential_id)))
        except Exception as exc:
            raise ConnectorRuntimeError(
                "Connector credential is missing or inactive.",
                detector_code="missing_connector_credential",
                input_data=redact_secret_values(input_data),
            ) from exc
        credential_config = decrypt_config(credential.encrypted_config)

    if connector_key == "http" and action_key == "request":
        return await _execute_http_request(action, input_data, credential_config)

    raise ConnectorRuntimeError(
        f"Connector action '{connector_key}.{action_key}' is not implemented.",
        detector_code="connector_action_not_found",
        input_data=redact_secret_values(input_data),
    )


async def _execute_http_request(
    action: dict[str, Any],
    input_data: dict[str, Any],
    credential_config: dict[str, Any] | None,
) -> ConnectorResult:
    start = perf_counter()
    safe_input = redact_secret_values(input_data)
    try:
        _validate_http_input(input_data)
        method = str(input_data.get("method", "GET")).upper()
        headers = dict(input_data.get("headers") or {})
        if credential_config:
            header_name = credential_config.get("header_name")
            header_value = credential_config.get("header_value")
            if header_name and header_value:
                headers[str(header_name)] = str(header_value)
        timeout = float(input_data.get("timeout_seconds") or 20)

        # IP-pinned request: the connection targets the already-validated public
        # address while SNI/Host stay the hostname, eliminating the DNS-rebinding
        # (TOCTOU) window. Redirects are never followed (no automatic rebind).
        response = await pinned_http_request(
            method,
            input_data["url"],
            headers=headers,
            params=input_data.get("query") if isinstance(input_data.get("query"), dict) else None,
            json_body=input_data.get("body") if input_data.get("body") is not None else None,
            timeout=timeout,
            allow_http=True,
        )

        status_code = int(response["status_code"])
        retryable_statuses = set(action.get("retry", {}).get("retryable_statuses", []))
        retryable = status_code in retryable_statuses
        text_preview = sanitize_error(str(response.get("body_text") or "")[:2048])
        body: Any = response.get("body_json")

        output = {
            "status_code": status_code,
            "headers": redact_secret_values(dict(response.get("headers") or {})),
            "body": redact_secret_values(body),
            "text_preview": text_preview,
        }
        if status_code >= 400:
            raise ConnectorRuntimeError(
                f"HTTP connector returned status {status_code}.",
                detector_code="connector_http_error",
                retryable=retryable,
                input_data=safe_input,
                output_data=output,
            )
        return ConnectorResult(
            connector_key="http",
            action_key="request",
            input_data=safe_input,
            output_data=output,
            duration_ms=int((perf_counter() - start) * 1000),
            retryable=retryable,
        )
    except ConnectorRuntimeError as exc:
        exc.input_data = exc.input_data or safe_input
        exc.output_data = exc.output_data or {"error": exc.sanitized_error}
        raise
    except Exception as exc:
        raise ConnectorRuntimeError(
            sanitize_error(str(exc)),
            input_data=safe_input,
            output_data={"error": sanitize_error(str(exc))},
        ) from exc
