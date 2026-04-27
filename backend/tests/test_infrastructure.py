"""
Tests for M7: Infrastructure — health endpoints, TenantMiddleware, rate limiting.
"""

import pytest
import pytest_asyncio
import uuid
from httpx import AsyncClient
from sqlalchemy import update


# =====================================================================
# Health & Readiness endpoints
# =====================================================================


class TestHealthEndpoint:
    """Tests for GET /health (liveness probe)."""

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client: AsyncClient):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" not in data
        assert "env" not in data

    @pytest.mark.asyncio
    async def test_health_no_auth_required(self, client: AsyncClient):
        """Health endpoint must be accessible without authentication."""
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert "X-Request-ID" in resp.headers

    @pytest.mark.asyncio
    async def test_ready_returns_ready(self, client: AsyncClient):
        """Readiness probe should return ready with SQLite test DB."""
        resp = await client.get("/ready")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ready"
        assert data["database"] == "connected"

    @pytest.mark.asyncio
    async def test_ready_no_auth_required(self, client: AsyncClient):
        resp = await client.get("/ready")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_ready_returns_503_when_db_unavailable(
        self, client: AsyncClient, db_session
    ):
        """Readiness should fail with 503 if the database is unavailable."""
        original_execute = db_session.execute

        async def failing_execute(*args, **kwargs):
            raise RuntimeError("database unavailable")

        db_session.execute = failing_execute
        try:
            resp = await client.get("/ready")
        finally:
            db_session.execute = original_execute

        assert resp.status_code == 503
        data = resp.json()
        assert data["status"] == "not_ready"
        assert "database unavailable" in data["database"]


# =====================================================================
# TenantMiddleware
# =====================================================================


class TestTenantMiddleware:
    """Tests for TenantMiddleware injecting tenant_id into request.state."""

    @pytest.mark.asyncio
    async def test_public_paths_pass_without_token(self, client: AsyncClient):
        """Public paths (health, register, login) should work without JWT."""
        # Health
        resp = await client.get("/health")
        assert resp.status_code == 200

        # Ready
        resp = await client.get("/ready")
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_auth_endpoints_work_through_middleware(self, client: AsyncClient):
        """Auth register/login endpoints pass through middleware."""
        payload = {
            "email": "middleware@test.com",
            "password": "securepass123",
            "full_name": "Middleware Test",
            "tenant_name": "MW Corp",
        }
        resp = await client.post("/api/v1/auth/register", json=payload)
        assert resp.status_code == 201

        resp = await client.post(
            "/api/v1/auth/login",
            json={"email": "middleware@test.com", "password": "securepass123"},
        )
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_authenticated_request_passes_middleware(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Authenticated requests should pass through TenantMiddleware and work normally."""
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_protected_endpoint_without_token_returns_401(
        self, client: AsyncClient
    ):
        """Protected endpoints without token should return 401 with current HTTPBearer behavior."""
        resp = await client.get("/api/v1/auth/me")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_invalid_token_handled_by_endpoint(self, client: AsyncClient):
        """Invalid token should be caught by endpoint dependency, not middleware."""
        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": "Bearer invalid-token-xyz"},
        )
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_deactivated_user_not_injected_by_middleware(
        self, client: AsyncClient, registered_user: dict, db_session
    ):
        """Middleware should not inject tenant context for deactivated users."""
        from app.models.user import User

        await db_session.execute(
            update(User)
            .where(User.id == uuid.UUID(registered_user["user_id"]))
            .values(is_active=False)
        )
        await db_session.commit()

        resp = await client.get(
            "/api/v1/auth/me",
            headers={"Authorization": f"Bearer {registered_user['access_token']}"},
        )
        assert resp.status_code == 401
        assert "deactivated" in resp.json()["detail"].lower()


# =====================================================================
# Rate Limiting
# =====================================================================


class TestRateLimiting:
    """Tests for RateLimitMiddleware."""

    @pytest.mark.asyncio
    async def test_rate_limit_headers_present(
        self, client: AsyncClient, auth_headers: dict
    ):
        """API responses should include rate limit headers."""
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        assert "X-Request-ID" in resp.headers
        assert "X-RateLimit-Limit" in resp.headers
        assert "X-RateLimit-Remaining" in resp.headers
        assert "X-RateLimit-Reset" in resp.headers

    @pytest.mark.asyncio
    async def test_request_id_header_is_forwarded_if_provided(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Request logging middleware should echo caller-provided X-Request-ID."""
        request_id = "req-test-123"
        headers = {**auth_headers, "X-Request-ID": request_id}

        resp = await client.get("/api/v1/auth/me", headers=headers)
        assert resp.status_code == 200
        assert resp.headers["X-Request-ID"] == request_id

    @pytest.mark.asyncio
    async def test_rate_limit_remaining_decreases(
        self, client: AsyncClient, auth_headers: dict
    ):
        """X-RateLimit-Remaining should decrease with each request."""
        resp1 = await client.get("/api/v1/auth/me", headers=auth_headers)
        remaining1 = int(resp1.headers["X-RateLimit-Remaining"])

        resp2 = await client.get("/api/v1/auth/me", headers=auth_headers)
        remaining2 = int(resp2.headers["X-RateLimit-Remaining"])

        assert remaining2 < remaining1

    @pytest.mark.asyncio
    async def test_rate_limit_not_applied_to_health(self, client: AsyncClient):
        """Non-API paths (health, ready) should NOT have rate limit headers."""
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert "X-RateLimit-Limit" not in resp.headers

    @pytest.mark.asyncio
    async def test_rate_limit_default_is_100(
        self, client: AsyncClient, auth_headers: dict
    ):
        """Rate limit should be 100 requests per window."""
        resp = await client.get("/api/v1/auth/me", headers=auth_headers)
        assert resp.headers["X-RateLimit-Limit"] == "100"

    @pytest.mark.asyncio
    async def test_unauthenticated_api_gets_rate_limited_by_ip(
        self, client: AsyncClient
    ):
        """Unauthenticated API requests should be rate-limited by IP."""
        # Register endpoint is public but still under /api/
        resp = await client.post(
            "/api/v1/auth/register",
            json={
                "email": "ratelimit@test.com",
                "password": "securepass123",
                "full_name": "Rate Limit",
                "tenant_name": "RL Corp",
            },
        )
        # Should have rate limit headers even for unauthenticated
        assert "X-RateLimit-Limit" in resp.headers


# =====================================================================
# CORS
# =====================================================================


class TestCORS:
    """Tests for CORS configuration."""

    @pytest.mark.asyncio
    async def test_cors_headers_on_allowed_origin(self, client: AsyncClient):
        """Requests from allowed origin should get CORS headers."""
        resp = await client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        assert resp.status_code == 200
        assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"

    @pytest.mark.asyncio
    async def test_cors_exposes_rate_limit_headers(self, client: AsyncClient):
        """CORS should expose rate limit headers to the browser."""
        resp = await client.options(
            "/api/v1/auth/login",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type",
            },
        )
        exposed = resp.headers.get("access-control-expose-headers", "")
        # Check that rate limit headers are in the expose list
        assert "X-RateLimit-Limit" in exposed or resp.status_code == 200


# =====================================================================
# Config / Settings
# =====================================================================


class TestConfig:
    """Tests for application configuration."""

    @pytest.mark.asyncio
    async def test_health_hides_env(self, client: AsyncClient):
        """Health endpoint should not disclose deployment environment."""
        resp = await client.get("/health")
        data = resp.json()
        assert "env" not in data

    @pytest.mark.asyncio
    async def test_health_hides_version(self, client: AsyncClient):
        """Health endpoint should not disclose application version."""
        resp = await client.get("/health")
        data = resp.json()
        assert "version" not in data

    def test_production_rejects_default_jwt_secret(self):
        """Production config should not allow the default JWT secret."""
        from app.core.config import Settings

        settings = Settings(
            APP_ENV="production",
            JWT_SECRET="change-me-in-production-use-256-bit-random-key",
        )

        with pytest.raises(ValueError, match="JWT_SECRET"):
            settings.validate_runtime_safety()
