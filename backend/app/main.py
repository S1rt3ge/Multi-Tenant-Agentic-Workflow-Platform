from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.api.v1.auth import router as auth_router
from app.api.v1.tenants import router as tenants_router

settings = get_settings()


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agentic Workflow Platform",
        description="Multi-tenant platform for visual agentic workflow design, execution and monitoring",
        version="0.1.0",
    )

    # CORS
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers — API v1
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(tenants_router, prefix="/api/v1")

    @app.get("/health")
    async def health_check():
        return {"status": "ok"}

    return app


app = create_app()
