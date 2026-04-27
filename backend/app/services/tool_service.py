import re
import time
import copy
from uuid import UUID
from typing import Any
from types import SimpleNamespace

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.engine.tools.executor import execute_tool
from app.engine.tools.safe_http import assert_safe_api_url, resolve_public_addresses, safe_http_request
from app.models.tool_registry import ToolRegistry


# ---------------------------------------------------------------------------
# Config masking (hide passwords/secrets on GET)
# ---------------------------------------------------------------------------

_CONNECTION_STRING_RE = re.compile(
    r"(://[^:]+:)([^@]+)(@)"
)


def _assert_safe_api_url(url: str, *, resolve_host: bool = False) -> None:
    from urllib.parse import urlparse

    try:
        assert_safe_api_url(url)
        if resolve_host:
            parsed = urlparse(url)
            resolve_public_addresses(parsed.hostname or "", parsed.port)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


def _is_masked_placeholder(value: Any) -> bool:
    return isinstance(value, str) and "****" in value


def _merge_api_config(existing_config: dict, incoming_config: dict) -> dict:
    merged = copy.deepcopy(existing_config)

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


def _tool_response(tool: ToolRegistry):
    return SimpleNamespace(
        id=tool.id,
        tenant_id=tool.tenant_id,
        name=tool.name,
        description=tool.description,
        tool_type=tool.tool_type,
        config=_mask_config(tool.config, tool.tool_type),
        is_active=tool.is_active,
        created_at=tool.created_at,
        updated_at=tool.updated_at,
    )


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
        method = config.get("method", "GET").upper()
        if method not in ("GET", "POST", "PUT", "DELETE"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Method must be GET, POST, PUT, or DELETE",
            )
        _assert_safe_api_url(url)

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
            ToolRegistry.is_active == True,  # noqa: E712
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

    return _tool_response(tool)


async def list_tools(db: AsyncSession, tenant_id: UUID) -> list[ToolRegistry]:
    """List all active tools for a tenant. Masks sensitive config values."""
    result = await db.execute(
        select(ToolRegistry)
        .where(ToolRegistry.tenant_id == tenant_id, ToolRegistry.is_active == True)  # noqa: E712
        .order_by(ToolRegistry.created_at)
    )
    tools = list(result.scalars().all())

    return [_tool_response(tool) for tool in tools]


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
                ToolRegistry.is_active == True,  # noqa: E712
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

    return _tool_response(tool)


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

    result = await execute_tool(tool_type, config, test_input or "")
    return {
        "success": result.get("success", False),
        "response": result.get("output", ""),
        "latency_ms": result.get("latency_ms", round((time.time() - start) * 1000, 2)),
    }


async def _test_api_tool(config: dict, test_input: str | None, start: float) -> dict:
    """Test an API tool by making a real HTTP request."""
    url = config.get("url", "")
    method = config.get("method", "GET").upper()
    headers = config.get("headers", {})
    body_template = config.get("body_template", "")

    _assert_safe_api_url(url, resolve_host=True)

    body = None
    if body_template and test_input:
        body = body_template.replace("{input}", test_input)

    try:
        resp = await safe_http_request(method=method, url=url, headers=headers, body=body, timeout=10.0)
        elapsed = (time.time() - start) * 1000

        response_data = resp["body_json"] if resp["body_json"] is not None else resp["body_text"]

        return {
            "success": 200 <= resp["status_code"] < 400,
            "response": {"status_code": resp["status_code"], "body": response_data},
            "latency_ms": round(elapsed, 2),
        }
    except TimeoutError:
        elapsed = (time.time() - start) * 1000
        return {"success": False, "response": "Tool unreachable (timeout 10s)", "latency_ms": round(elapsed, 2)}
    except Exception as e:
        elapsed = (time.time() - start) * 1000
        return {"success": False, "response": str(e), "latency_ms": round(elapsed, 2)}
