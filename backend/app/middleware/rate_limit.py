"""
Rate Limiting middleware.

Per-tenant rate limiting: 100 requests/min on API endpoints.
Uses in-memory sliding window counter. For production with multiple
backend instances, replace with Redis-based counter.
"""

import time
from collections import defaultdict
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    In-memory sliding window rate limiter.
    Limits per tenant (identified by request.state.tenant_id).
    Unauthenticated requests are limited by client IP.

    Config:
        max_requests: max requests per window (default 100)
        window_seconds: sliding window duration (default 60)
    """

    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        # key -> list of timestamps
        self._request_log: dict[str, list[float]] = defaultdict(list)

    def _get_key(self, request: Request) -> str:
        """Get rate limit key: tenant_id if authenticated, else client IP."""
        tenant_id = getattr(request.state, "tenant_id", None)
        if tenant_id:
            return f"tenant:{tenant_id}"
        # Fallback to client IP
        client_host = request.client.host if request.client else "unknown"
        return f"ip:{client_host}"

    def _cleanup(self, key: str, now: float) -> None:
        """Remove timestamps outside the current window."""
        cutoff = now - self.window_seconds
        timestamps = self._request_log[key]
        # Find the first index within the window
        idx = 0
        for i, ts in enumerate(timestamps):
            if ts >= cutoff:
                idx = i
                break
        else:
            # All timestamps are outside the window
            idx = len(timestamps)
        self._request_log[key] = timestamps[idx:]

    async def dispatch(self, request: Request, call_next):
        # Only rate-limit API paths
        if not request.url.path.startswith("/api/"):
            return await call_next(request)

        # Skip OPTIONS (CORS preflight)
        if request.method == "OPTIONS":
            return await call_next(request)

        now = time.monotonic()
        key = self._get_key(request)

        # Cleanup old entries
        self._cleanup(key, now)

        # Check limit
        if len(self._request_log[key]) >= self.max_requests:
            retry_after = int(self.window_seconds - (now - self._request_log[key][0]))
            return JSONResponse(
                status_code=429,
                content={"detail": f"Rate limit exceeded. Try again in {max(1, retry_after)}s."},
                headers={"Retry-After": str(max(1, retry_after))},
            )

        # Record this request
        self._request_log[key].append(now)

        response = await call_next(request)

        # Add rate limit headers
        remaining = self.max_requests - len(self._request_log[key])
        response.headers["X-RateLimit-Limit"] = str(self.max_requests)
        response.headers["X-RateLimit-Remaining"] = str(max(0, remaining))
        response.headers["X-RateLimit-Reset"] = str(self.window_seconds)

        return response
