from fastapi import Depends, FastAPI
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db, async_session_factory
from app.core.logging import setup_logging
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.tenant import TenantMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.api.v1.auth import router as auth_router
from app.api.v1.tenants import router as tenants_router
from app.api.v1.workflows import router as workflows_router
from app.api.v1.tools import router as tools_router
from app.api.v1.agents import router as agents_router
from app.api.v1.executions import router as executions_router
from app.api.v1.analytics import router as analytics_router

settings = get_settings()


def create_app() -> FastAPI:
    settings.validate_runtime_safety()
    setup_logging(level=settings.LOG_LEVEL, fmt=settings.LOG_FORMAT)

    app = FastAPI(
        title="Agentic Workflow Platform",
        description="Multi-tenant platform for visual agentic workflow design, execution and monitoring",
        version="0.1.0",
    )
    app.state.db_session_factory = async_session_factory

    # --- Middleware (order matters: last added = first executed) ---

    # 0. Request Logging (outermost — captures final status and timing)
    app.add_middleware(RequestLoggingMiddleware)

    # 1. CORS (outermost — handles preflight before anything else)
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ],
    )

    # 2. Rate Limiting (after CORS, before tenant resolution)
    app.add_middleware(RateLimitMiddleware, max_requests=100, window_seconds=60)

    # 3. Tenant Middleware (innermost — resolves tenant from JWT)
    app.add_middleware(TenantMiddleware)

    # --- Routers — API v1 ---
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(tenants_router, prefix="/api/v1")
    app.include_router(workflows_router, prefix="/api/v1")
    app.include_router(tools_router, prefix="/api/v1")
    app.include_router(agents_router, prefix="/api/v1")
    app.include_router(executions_router, prefix="/api/v1")
    app.include_router(analytics_router, prefix="/api/v1")

    # --- Health & Readiness ---

    @app.get("/health", tags=["infrastructure"])
    async def health_check():
        """
        Liveness probe. Returns 200 if the application process is running.
        Does NOT check external dependencies (use /ready for that).
        """
        return {
            "status": "ok",
            "version": "0.1.0",
            "env": settings.APP_ENV,
        }

    @app.get("/ready", tags=["infrastructure"])
    async def readiness_check(db: AsyncSession = Depends(get_db)):
        """
        Readiness probe. Verifies the application can serve traffic by
        checking connectivity to the database.
        """
        try:
            await db.execute(text("SELECT 1"))
            return {"status": "ready", "database": "connected"}
        except Exception as e:
            return JSONResponse(
                status_code=503,
                content={"status": "not_ready", "database": str(e)},
            )

    return app


app = create_app()
