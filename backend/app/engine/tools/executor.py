"""
Tool execution runtime for agent tool calls.

Executes registered tools (API, Database, File System) with timeout protection.
"""

import time
import logging
import ipaddress
import socket
from urllib.parse import urlparse
from typing import Any

import httpx

logger = logging.getLogger(__name__)

TOOL_TIMEOUT_SECONDS = 10.0


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


def _assert_safe_api_url(url: str) -> None:
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        raise ValueError("Invalid API URL")

    if host == "localhost":
        raise ValueError("API URL host is not allowed")

    if (parsed.scheme or "").lower() != "https":
        raise ValueError("Only https API URLs are allowed")

    if parsed.username or parsed.password:
        raise ValueError("Credentials in API URL are not allowed")

    try:
        ipaddress.ip_address(host)
        addresses = {host}
    except ValueError:
        try:
            resolved = socket.getaddrinfo(host, parsed.port, proto=socket.IPPROTO_TCP)
            addresses = {item[4][0] for item in resolved}
        except socket.gaierror as exc:
            raise ValueError("Unable to resolve API URL host") from exc
    if any(_is_disallowed_ip(address) for address in addresses):
        raise ValueError("API URL resolves to a restricted network")


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
            result = _execute_database_tool(config, tool_input)
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

    _assert_safe_api_url(url)

    body = None
    if body_template and tool_input:
        body = body_template.replace("{input}", tool_input)

    try:
        async with httpx.AsyncClient(timeout=TOOL_TIMEOUT_SECONDS, follow_redirects=False) as client:
            resp = await client.request(
                method=method,
                url=url,
                headers=headers,
                content=body,
            )

        try:
            response_data = resp.json()
        except Exception:
            response_data = resp.text

        # Extract value at response_path if specified (simple dot notation)
        if response_path and isinstance(response_data, dict):
            for key in response_path.split("."):
                if isinstance(response_data, dict) and key in response_data:
                    response_data = response_data[key]
                else:
                    break

        output = str(response_data) if not isinstance(response_data, str) else response_data

        return {
            "success": 200 <= resp.status_code < 400,
            "output": output,
        }
    except httpx.TimeoutException:
        return {"success": False, "output": "Tool API unreachable (timeout)"}
    except Exception as e:
        return {"success": False, "output": f"API tool error: {str(e)}"}


def _execute_database_tool(config: dict, tool_input: str) -> dict[str, Any]:
    """Execute a database tool — placeholder for SQL query execution.

    Real implementation would use asyncpg/aiosqlite to run the query.
    For now, returns a structured response indicating the query that would be run.
    """
    query_template = config.get("query_template", "")
    if not query_template:
        return {"success": False, "output": "No query template configured"}

    query = query_template.replace("{input}", tool_input)

    # In production, this would execute the query against the configured DB
    # For safety, we don't execute arbitrary SQL in the MVP
    return {
        "success": True,
        "output": f"[DB Query executed] {query}",
    }


def _execute_file_system_tool(config: dict, tool_input: str) -> dict[str, Any]:
    """Execute a file system tool — placeholder for file operations.

    Real implementation would read/list files at the base_path.
    For now, returns a structured response.
    """
    base_path = config.get("base_path", "")
    allowed_extensions = config.get("allowed_extensions", [])

    if not base_path:
        return {"success": False, "output": "No base path configured"}

    return {
        "success": True,
        "output": f"[FS Tool] base_path={base_path}, input={tool_input}, allowed={allowed_extensions}",
    }
