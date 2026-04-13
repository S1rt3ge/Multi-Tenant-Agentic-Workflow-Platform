"""
Shared test fixtures for the Agentic Workflow Platform backend.

Uses SQLite (aiosqlite) as an in-memory database for tests.
Overrides FastAPI dependencies to inject the test DB session.
"""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, String, DateTime, TIMESTAMP
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB as PG_JSONB

from app.core.database import Base, get_db
from app.main import create_app

# ---------------------------------------------------------------------------
# SQLite type compilation overrides
# ---------------------------------------------------------------------------
# PostgreSQL UUID -> store as CHAR(36) in SQLite
# PostgreSQL TIMESTAMPTZ -> store as DateTime in SQLite

from sqlalchemy.ext.compiler import compiles


@compiles(PG_UUID, "sqlite")
def compile_uuid_sqlite(type_, compiler, **kw):
    return "CHAR(36)"


@compiles(TIMESTAMP, "sqlite")
def compile_timestamptz_sqlite(type_, compiler, **kw):
    return "DATETIME"


@compiles(PG_JSONB, "sqlite")
def compile_jsonb_sqlite(type_, compiler, **kw):
    return "TEXT"


# ---------------------------------------------------------------------------
# Test engine (in-memory SQLite)
# ---------------------------------------------------------------------------
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture(autouse=True)
async def setup_database():
    """Create all tables before each test, drop after."""

    @event.listens_for(test_engine.sync_engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with test_engine.begin() as conn:
        # Import models so Base.metadata knows about them
        from app.models import Tenant, User, Workflow, ToolRegistry, AgentConfig  # noqa: F401

        await conn.run_sync(Base.metadata.create_all)

    yield

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

    await test_engine.dispose()


@pytest_asyncio.fixture
async def db_session() -> AsyncSession:
    """Provide a transactional test DB session."""
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture
async def client(db_session: AsyncSession):
    """Provide an httpx AsyncClient wired to the FastAPI test app."""
    app = create_app()

    async def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Auth helper fixtures
# ---------------------------------------------------------------------------

OWNER_EMAIL = "owner@test.com"
OWNER_PASSWORD = "securepass123"
OWNER_NAME = "Test Owner"
TENANT_NAME = "Test Corp"


@pytest_asyncio.fixture
async def registered_user(client: AsyncClient) -> dict:
    """Register a user via API and return response data + credentials."""
    payload = {
        "email": OWNER_EMAIL,
        "password": OWNER_PASSWORD,
        "full_name": OWNER_NAME,
        "tenant_name": TENANT_NAME,
    }
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 201, f"Registration failed: {resp.text}"
    data = resp.json()
    data["email"] = payload["email"]
    data["password"] = payload["password"]
    return data


@pytest_asyncio.fixture
async def auth_headers(registered_user: dict) -> dict:
    """Return Authorization header dict for the registered owner."""
    return {"Authorization": f"Bearer {registered_user['access_token']}"}


@pytest_asyncio.fixture
async def owner_and_editor(client: AsyncClient, auth_headers: dict) -> dict:
    """Register owner, then invite an editor. Returns owner headers + editor data."""
    invite_resp = await client.post(
        "/api/v1/tenants/invite",
        json={"email": "editor@test.com", "role": "editor"},
        headers=auth_headers,
    )
    assert invite_resp.status_code == 201, f"Invite failed: {invite_resp.text}"
    editor = invite_resp.json()
    return {
        "owner_headers": auth_headers,
        "editor": editor,
    }
