"""
Tool execution runtime for agent tool calls.

Executes registered tools (API, Database, File System) with timeout protection.
"""

import time
import logging
import json
import asyncio
from pathlib import Path
from urllib.parse import urlparse
from typing import Any

import asyncpg
import aiosqlite

from app.engine.tools.safe_http import assert_safe_api_url, safe_http_request

logger = logging.getLogger(__name__)

TOOL_TIMEOUT_SECONDS = 10.0


MAX_DB_ROWS = 100
MAX_FILE_BYTES = 100_000


async def execute_tool(tool_type: str, config: dict, tool_input: str) -> dict[str, Any]:
    """Execute a tool based on its type and config.

    Args:
        tool_type: One of 'api', 'database', 'file_system'.
        config: Tool configuration from ToolRegistry.config.
        tool_input: Input string from the agent.

    Returns:
        Dict with keys: success (bool), output (str), latency_ms (int).
    """
    start = time.time()

    try:
        if tool_type == "api":
            result = await _execute_api_tool(config, tool_input)
        elif tool_type == "database":
            result = await _execute_database_tool(config, tool_input)
        elif tool_type == "file_system":
            result = _execute_file_system_tool(config, tool_input)
        else:
            result = {"success": False, "output": f"Unknown tool type: {tool_type}"}
    except Exception as e:
        logger.error(f"Tool execution error: {e}")
        result = {"success": False, "output": f"Tool execution error: {str(e)}"}

    elapsed = int((time.time() - start) * 1000)
    result["latency_ms"] = elapsed
    return result


async def _execute_api_tool(config: dict, tool_input: str) -> dict[str, Any]:
    """Execute an API tool — make HTTP request per config."""
    url = config.get("url", "")
    method = config.get("method", "GET").upper()
    headers = config.get("headers", {})
    body_template = config.get("body_template", "")
    response_path = config.get("response_path", "")

    assert_safe_api_url(url)

    body = None
    if body_template and tool_input:
        body = body_template.replace("{input}", tool_input)

    try:
        resp = await safe_http_request(
            method=method,
            url=url,
            headers=headers,
            body=body,
            timeout=TOOL_TIMEOUT_SECONDS,
        )
        response_data = resp["body_json"] if resp["body_json"] is not None else resp["body_text"]

        # Extract value at response_path if specified (simple dot notation)
        if response_path and isinstance(response_data, dict):
            for key in response_path.split("."):
                if isinstance(response_data, dict) and key in response_data:
                    response_data = response_data[key]
                else:
                    break

        output = str(response_data) if not isinstance(response_data, str) else response_data

        return {
            "success": 200 <= resp["status_code"] < 400,
            "output": output,
        }
    except TimeoutError:
        return {"success": False, "output": "Tool API unreachable (timeout)"}
    except Exception as e:
        return {"success": False, "output": f"API tool error: {str(e)}"}


def _render_read_only_query(query_template: str, tool_input: str, placeholder: str) -> tuple[str, list[str]]:
    query = query_template.strip()
    params: list[str] = []
    if "{input}" in query:
        query = query.replace("{input}", placeholder)
        params.append(tool_input)

    lowered = query.lstrip().lower()
    if not lowered.startswith(("select", "with", "show", "pragma")):
        raise ValueError("Only read-only database queries are allowed")
    if ";" in query.rstrip(";"):
        raise ValueError("Multiple SQL statements are not allowed")
    return query, params


async def _execute_database_tool(config: dict, tool_input: str) -> dict[str, Any]:
    """Execute a read-only query against PostgreSQL or SQLite."""
    connection_string = config.get("connection_string", "")
    query_template = config.get("query_template", "")
    if not connection_string:
        return {"success": False, "output": "No connection string configured"}
    if not query_template:
        return {"success": False, "output": "No query template configured"}

    parsed = urlparse(connection_string)
    try:
        if parsed.scheme.startswith("postgres"):
            query, params = _render_read_only_query(query_template, tool_input, "$1")
            conn = await asyncpg.connect(connection_string, timeout=TOOL_TIMEOUT_SECONDS)
            try:
                rows = await asyncio.wait_for(conn.fetch(query, *params), timeout=TOOL_TIMEOUT_SECONDS)
                data = [dict(row) for row in rows[:MAX_DB_ROWS]]
            finally:
                await conn.close()
        elif parsed.scheme in {"sqlite", "sqlite3"}:
            query, params = _render_read_only_query(query_template, tool_input, "?")
            db_path = parsed.path or ":memory:"
            async with aiosqlite.connect(db_path) as conn:
                conn.row_factory = aiosqlite.Row
                cursor = await asyncio.wait_for(conn.execute(query, params), timeout=TOOL_TIMEOUT_SECONDS)
                rows = await asyncio.wait_for(cursor.fetchmany(MAX_DB_ROWS), timeout=TOOL_TIMEOUT_SECONDS)
                await cursor.close()
                data = [dict(row) for row in rows]
        else:
            return {"success": False, "output": "Unsupported database connection string"}
    except Exception as exc:
        return {"success": False, "output": f"Database tool error: {str(exc)}"}

    return {"success": True, "output": json.dumps(data, default=str)}


def _execute_file_system_tool(config: dict, tool_input: str) -> dict[str, Any]:
    """Read or list files under the configured base_path."""
    base_path = config.get("base_path", "")
    allowed_extensions = config.get("allowed_extensions", [])

    if not base_path:
        return {"success": False, "output": "No base path configured"}

    try:
        base = Path(base_path).expanduser().resolve()
        requested = (tool_input or ".").strip() or "."
        requested_path = Path(requested)
        if requested_path.is_absolute():
            return {"success": False, "output": "Absolute paths are not allowed"}
        target = (base / requested_path).resolve()
        if base != target and base not in target.parents:
            return {"success": False, "output": "Path escapes configured base_path"}
        if not target.exists():
            return {"success": False, "output": "Path does not exist"}

        normalized_exts = {str(ext).lower() for ext in allowed_extensions}
        if target.is_file() and normalized_exts and target.suffix.lower() not in normalized_exts:
            return {"success": False, "output": "File extension is not allowed"}
        if target.is_dir():
            entries = [
                {"name": child.name, "type": "directory" if child.is_dir() else "file"}
                for child in sorted(target.iterdir(), key=lambda item: item.name)[:MAX_DB_ROWS]
            ]
            return {"success": True, "output": json.dumps(entries)}

        content = target.read_bytes()[:MAX_FILE_BYTES]
        return {"success": True, "output": content.decode("utf-8", errors="replace")}
    except Exception as exc:
        return {"success": False, "output": f"File system tool error: {str(exc)}"}
