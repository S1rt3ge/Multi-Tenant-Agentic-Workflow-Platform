import logging
import time
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware


logger = logging.getLogger("app.request")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log one structured line per request with request correlation metadata."""

    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID", str(uuid4()))
        request.state.request_id = request_id

        start = time.perf_counter()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            path = request.url.path
            status_code = response.status_code if response else 500

            if response is not None:
                response.headers["X-Request-ID"] = request_id

            if path == "/health":
                continue_logging = False
            else:
                continue_logging = True

            if continue_logging:
                logger.info(
                    "request_completed",
                    extra={
                        "request_id": request_id,
                        "method": request.method,
                        "path": path,
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                        "tenant_id": getattr(request.state, "tenant_id", None),
                        "user_id": getattr(request.state, "user_id", None),
                        "client_ip": request.client.host if request.client else None,
                    },
                )
