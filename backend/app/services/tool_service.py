import re
import time
import copy
import ipaddress
import socket
from uuid import UUID
from typing import Any

import httpx
from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.models.tool_registry import ToolRegistry


# ---------------------------------------------------------------------------
# Config masking (hide passwords/secrets on GET)
# ---------------------------------------------------------------------------

_CONNECTION_STRING_RE = re.compile(
    r"(://[^:]+:)([^@]+)(@)"
)


def _resolve_host_addresses(host: str, port: int | None) -> set[str]:
    try:
        resolved = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to resolve URL host",
        ) from exc
    return {item[4][0] for item in resolved}


def _is_disallowed_ip(ip_value: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_value)
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


def _assert_safe_api_url(url: str, *, resolve_host: bool = False) -> None:
    from urllib.parse import urlparse

    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid URL format",
        )

    if host == "localhost":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL host is not allowed",
        )

    scheme = (parsed.scheme or "").lower()
    if scheme != "https":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Only https API URLs are allowed",
        )

    if parsed.username or parsed.password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Credentials in API URL are not allowed",
        )

    # If host is a literal IP, block private/sensitive ranges.
    try:
        ipaddress.ip_address(host)
        addresses = {host}
    except ValueError:
        if not resolve_host:
            return
        addresses = _resolve_host_addresses(host, parsed.port)

    if any(_is_disallowed_ip(address) for address in addresses):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="URL host resolves to a restricted network",
        )


def _is_masked_placeholder(value: Any) -> bool:
    return isinstance(value, str) and "****" in value


def _merge_api_config(existing_config: dict, incoming_config: dict) -> dict:
    merged = copy.deepcopy(existing_config)

    if "url" not in incoming_config:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Config 'url' is required for API tools",
        )

    for key, value in incoming_config.items():
        if key == "headers" and isinstance(value, dict):
            existing_headers = merged.get("headers", {})
            incoming_headers = value
            next_headers = {}

            for header_key, header_value in incoming_headers.items():
                if _is_masked_placeholder(header_value) and header_key in existing_headers:
                    next_headers[header_key] = existing_headers[header_key]
                else:
                    next_headers[header_key] = header_value

            merged["headers"] = next_headers
            continue

        if key == "url" and isinstance(value, str):
            _assert_safe_api_url(value)

        merged[key] = value

    return merged


def _merge_database_config(existing_config: dict, incoming_config: dict) -> dict:
    merged = copy.deepcopy(existing_config)

    for key, value in incoming_config.items():
        if key == "connection_string" and _is_masked_placeholder(value):
            continue
        merged[key] = value

    return merged


def _mask_config(config: dict, tool_type: str) -> dict:
    """Return a copy of config with sensitive values masked."""
    masked = copy.deepcopy(config)

    if tool_type == "database" and "connection_string" in masked:
        masked["connection_string"] = _CONNECTION_STRING_RE.sub(
            r"\1****\3", masked["connection_string"]
        )

    if tool_type == "api" and "headers" in masked and isinstance(masked["headers"], dict):
        sensitive_keys = {"authorization", "api-key", "x-api-key", "apikey"}
        for key in masked["headers"]:
            if key.lower() in sensitive_keys:
                masked["headers"][key] = "****"

    return masked


# ---------------------------------------------------------------------------
# Config validation
# ---------------------------------------------------------------------------

def _validate_config(tool_type: str, config: dict) -> None:
    """Validate config fields based on tool_type."""
    if tool_type == "api":
        url = config.get("url")
        if not url or not isinstance(url, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Config 'url' is required for API tools",
            )
        if not url.startswith(("http://", "https://")):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid URL format",
            )
        _assert_safe_api_url(url)
        method = config.get("method", "GET").upper()
        if method not in ("GET", "POST", "PUT", "DELETE"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Method must be GET, POST, PUT, or DELETE",
            )

    elif tool_type == "database":
        if not config.get("connection_string"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Config 'connection_string' is required for database tools",
            )

    elif tool_type == "file_system":
        if not config.get("base_path"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Config 'base_path' is required for file_system tools",
            )


# ---------------------------------------------------------------------------
# CRUD
# ---------------------------------------------------------------------------

async def create_tool(
    db: AsyncSession,
    tenant_id: UUID,
    name: str,
    description: str,
    tool_type: str,
    config: dict,
) -> ToolRegistry:
    """Create a new tool after validating config and checking name uniqueness."""
    _validate_config(tool_type, config)

    # Check unique name within tenant
    existing = await db.execute(
        select(ToolRegistry).where(
            ToolRegistry.tenant_id == tenant_id,
            ToolRegistry.name == name,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tool with name '{name}' already exists",
        )

    tool = ToolRegistry(
        tenant_id=tenant_id,
        name=name,
        description=description,
        tool_type=tool_type,
        config=config,
    )
    db.add(tool)
    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tool with name '{name}' already exists",
        ) from exc
    await db.refresh(tool)

    # Mask secrets in response
    tool.config = _mask_config(tool.config, tool.tool_type)
    return tool


async def list_tools(db: AsyncSession, tenant_id: UUID) -> list[ToolRegistry]:
    """List all active tools for a tenant. Masks sensitive config values."""
    result = await db.execute(
        select(ToolRegistry)
        .where(ToolRegistry.tenant_id == tenant_id, ToolRegistry.is_active == True)  # noqa: E712
        .order_by(ToolRegistry.created_at)
    )
    tools = list(result.scalars().all())

    for tool in tools:
        tool.config = _mask_config(tool.config, tool.tool_type)

    return tools


async def get_tool(db: AsyncSession, tenant_id: UUID, tool_id: UUID) -> ToolRegistry:
    """Get a tool by ID. Raises 404 if not found or wrong tenant."""
    result = await db.execute(
        select(ToolRegistry).where(
            ToolRegistry.id == tool_id,
            ToolRegistry.tenant_id == tenant_id,
            ToolRegistry.is_active == True,  # noqa: E712
        )
    )
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found"
        )
    return tool


async def update_tool(
    db: AsyncSession,
    tenant_id: UUID,
    tool_id: UUID,
    name: str | None = None,
    description: str | None = None,
    tool_type: str | None = None,
    config: dict | None = None,
) -> ToolRegistry:
    """Update a tool. Validates new config if provided."""
    tool = await get_tool(db, tenant_id, tool_id)

    # If changing name, check uniqueness
    if name is not None and name != tool.name:
        existing = await db.execute(
            select(ToolRegistry).where(
                ToolRegistry.tenant_id == tenant_id,
                ToolRegistry.name == name,
                ToolRegistry.id != tool_id,
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Tool with name '{name}' already exists",
            )
        tool.name = name

    if description is not None:
        tool.description = description

    effective_type = tool_type if tool_type is not None else tool.tool_type
    if config is not None:
        merged_config = config
        if tool.tool_type == "api" and effective_type == "api":
            merged_config = _merge_api_config(tool.config, config)
        elif tool.tool_type == "database" and effective_type == "database":
            merged_config = _merge_database_config(tool.config, config)

        _validate_config(effective_type, merged_config)
        tool.config = merged_config
    if tool_type is not None:
        if config is None:
            _validate_config(tool_type, tool.config)
        tool.tool_type = tool_type

    try:
        await db.commit()
    except IntegrityError as exc:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tool with name '{name or tool.name}' already exists",
        ) from exc
    await db.refresh(tool)

    tool.config = _mask_config(tool.config, tool.tool_type)
    return tool


async def delete_tool(db: AsyncSession, tenant_id: UUID, tool_id: UUID) -> None:
    """Soft-delete a tool."""
    tool = await get_tool(db, tenant_id, tool_id)
    tool.is_active = False
    await db.commit()


# ---------------------------------------------------------------------------
# Test tool
# ---------------------------------------------------------------------------

async def test_tool(
    db: AsyncSession, tenant_id: UUID, tool_id: UUID, test_input: str | None = None
) -> dict:
    """Execute a test call for the tool and return result with latency."""
    # Fetch raw tool (unmask) for real execution
    result = await db.execute(
        select(ToolRegistry).where(
            ToolRegistry.id == tool_id,
            ToolRegistry.tenant_id == tenant_id,
            ToolRegistry.is_active == True,  # noqa: E712
        )
    )
    tool = result.scalar_one_or_none()
    if tool is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Tool not found"
        )

    config = tool.config
    tool_type = tool.tool_type

    start = time.time()

    if tool_type == "api":
        return await _test_api_tool(config, test_input, start)
    elif tool_type == "database":
        return _test_database_tool(config, start)
    elif tool_type == "file_system":
        return _test_file_system_tool(config, start)
    else:
        elapsed = (time.time() - start) * 1000
        return {"success": False, "response": f"Unknown tool type: {tool_type}", "latency_ms": round(elapsed, 2)}


async def _test_api_tool(config: dict, test_input: str | None, start: float) -> dict:
    """Test an API tool by making a real HTTP request."""
    url = config.get("url", "")
    method = config.get("method", "GET").upper()
    headers = config.get("headers", {})
    body_template = config.get("body_template", "")

    _assert_safe_api_url(url)

    body = None
    if body_template and test_input:
        body = body_template.replace("{input}", test_input)

    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            resp = await client.request(
                method=method,
                url=url,
                headers=headers,
                content=body,
            )
        elapsed = (time.time() - start) * 1000

        try:
            response_data = resp.json()
        except Exception:
            response_data = resp.text

        return {
            "success": 200 <= resp.status_code < 400,
            "response": {"status_code": resp.status_code, "body": response_data},
            "latency_ms": round(elapsed, 2),
        }
    except httpx.TimeoutException:
        elapsed = (time.time() - start) * 1000
        return {"success": False, "response": "Tool unreachable (timeout 10s)", "latency_ms": round(elapsed, 2)}
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return {"success": False, "response": str(e), "latency_ms": round(elapsed, 2)}


def _test_database_tool(config: dict, start: float) -> dict:
    """Test a database tool — just validate the connection string format."""
    conn = config.get("connection_string", "")
    elapsed = (time.time() - start) * 1000
    if "://" in conn:
        return {"success": True, "response": "Connection string format is valid", "latency_ms": round(elapsed, 2)}
    return {"success": False, "response": "Invalid connection string format", "latency_ms": round(elapsed, 2)}


def _test_file_system_tool(config: dict, start: float) -> dict:
    """Test a file_system tool — validate base_path is set."""
    base_path = config.get("base_path", "")
    elapsed = (time.time() - start) * 1000
    if base_path:
        return {"success": True, "response": f"Base path configured: {base_path}", "latency_ms": round(elapsed, 2)}
    return {"success": False, "response": "Base path is empty", "latency_ms": round(elapsed, 2)}
