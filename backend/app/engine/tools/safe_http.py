import asyncio
import json
import socket
import ssl
import ipaddress
from urllib.parse import urlparse
from typing import Any


MAX_RESPONSE_BYTES = 1_000_000


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


def resolve_public_addresses(host: str, port: int | None) -> set[str]:
    try:
        resolved = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise ValueError("Unable to resolve API URL host") from exc

    addresses = {item[4][0] for item in resolved}
    if not addresses or any(_is_disallowed_ip(address) for address in addresses):
        raise ValueError("API URL resolves to a restricted network")
    return addresses


def assert_safe_api_url(url: str) -> None:
    parsed = urlparse(url)
    host = parsed.hostname
    if not host:
        raise ValueError("Invalid API URL")
    if host.lower() == "localhost":
        raise ValueError("API URL host is not allowed")
    if (parsed.scheme or "").lower() != "https":
        raise ValueError("Only https API URLs are allowed")
    if parsed.username or parsed.password:
        raise ValueError("Credentials in API URL are not allowed")

    try:
        ipaddress.ip_address(host)
        addresses = {host}
    except ValueError:
        addresses = resolve_public_addresses(host, parsed.port)

    if any(_is_disallowed_ip(address) for address in addresses):
        raise ValueError("API URL resolves to a restricted network")


def _clean_header_value(value: Any) -> str:
    text = str(value)
    if "\r" in text or "\n" in text:
        raise ValueError("HTTP header values cannot contain newlines")
    return text


async def safe_http_request(
    method: str,
    url: str,
    headers: dict[str, Any] | None = None,
    body: str | bytes | None = None,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Perform a minimal HTTPS request using a pre-resolved public IP.

    This avoids DNS rebinding between validation and connect because the TCP
    connection is made to the already validated address while TLS SNI remains
    the original hostname.
    """
    parsed = urlparse(url)
    assert_safe_api_url(url)

    host = parsed.hostname or ""
    port = parsed.port or 443
    address = sorted(resolve_public_addresses(host, port))[0]
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    method = method.upper()
    if method not in {"GET", "POST", "PUT", "DELETE"}:
        raise ValueError("Unsupported HTTP method")

    body_bytes = body.encode("utf-8") if isinstance(body, str) else (body or b"")
    request_headers = {
        "Host": host if port == 443 else f"{host}:{port}",
        "User-Agent": "GraphPilot/1.0",
        "Connection": "close",
    }
    for key, value in (headers or {}).items():
        key_text = str(key)
        if key_text.lower() in {"host", "connection", "content-length"}:
            continue
        if "\r" in key_text or "\n" in key_text or ":" in key_text:
            raise ValueError("Invalid HTTP header name")
        request_headers[key_text] = _clean_header_value(value)
    if body_bytes:
        request_headers["Content-Length"] = str(len(body_bytes))

    header_blob = "".join(f"{key}: {value}\r\n" for key, value in request_headers.items())
    request_blob = f"{method} {path} HTTP/1.1\r\n{header_blob}\r\n".encode("utf-8") + body_bytes

    ssl_context = ssl.create_default_context()
    reader: asyncio.StreamReader
    writer: asyncio.StreamWriter
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(address, port, ssl=ssl_context, server_hostname=host),
        timeout=timeout,
    )
    try:
        writer.write(request_blob)
        await asyncio.wait_for(writer.drain(), timeout=timeout)

        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = await asyncio.wait_for(reader.read(65536), timeout=timeout)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_RESPONSE_BYTES:
                raise ValueError("HTTP response exceeds maximum size")
            chunks.append(chunk)
    finally:
        writer.close()
        await writer.wait_closed()

    raw = b"".join(chunks)
    header_bytes, _, body_bytes = raw.partition(b"\r\n\r\n")
    header_text = header_bytes.decode("iso-8859-1", errors="replace")
    status_line = header_text.split("\r\n", 1)[0]
    parts = status_line.split(" ", 2)
    if len(parts) < 2 or not parts[1].isdigit():
        raise ValueError("Invalid HTTP response")

    body_text = body_bytes.decode("utf-8", errors="replace")
    try:
        body_json = json.loads(body_text)
    except Exception:
        body_json = None

    return {
        "status_code": int(parts[1]),
        "body_text": body_text,
        "body_json": body_json,
    }
