"""
TenantMiddleware: extracts tenant_id from JWT and injects into request.state.

For auth-free paths (register, login, refresh, health, ready, docs), middleware
passes through without checking JWT. For all other paths, the JWT is decoded
and request.state.tenant_id + request.state.user_id are set.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.security import decode_token

# Paths that do NOT require a tenant context
PUBLIC_PATHS = {
    "/health",
    "/ready",
    "/docs",
    "/openapi.json",
    "/redoc",
    "/api/v1/auth/register",
    "/api/v1/auth/login",
    "/api/v1/auth/refresh",
}


def _is_public(path: str) -> bool:
    """Check if the request path is public (no auth required)."""
    # Exact match
    if path in PUBLIC_PATHS:
        return True
    # Prefix match for docs sub-paths
    if path.startswith("/docs") or path.startswith("/redoc"):
        return True
    return False


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Middleware that:
    1. Extracts JWT from Authorization header
    2. Decodes to get user_id and tenant_id
    3. Injects tenant_id and user_id into request.state
    4. Passes through for public paths and OPTIONS (CORS preflight)
    """

    async def dispatch(self, request: Request, call_next):
        # Always pass through OPTIONS (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        # Pass through public paths
        if _is_public(request.url.path):
            return await call_next(request)

        # WebSocket connections are handled separately by endpoint auth
        if request.url.path.startswith("/ws/"):
            return await call_next(request)

        # Extract Authorization header
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            # Let the endpoint's own auth dependency handle the 401/403
            # This middleware is additive, not a gatekeeper
            return await call_next(request)

        token = auth_header[7:]  # Strip "Bearer "
        payload = decode_token(token)

        if payload and payload.get("type") == "access":
            request.state.tenant_id = payload.get("tenant_id")
            request.state.user_id = payload.get("sub")
        # If token is invalid, let endpoint dependencies handle it

        return await call_next(request)
