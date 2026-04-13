# Project Progress Tracker
# Last updated: 2026-04-13

## Current Status: M1 TESTING → NEEDS PYTHON ENVIRONMENT

## What's Done

### Spec-First Methodology (100%)
- [x] PROJECT_IDEA.md — idea document (10 sections)
- [x] TECH_SPEC.md — full spec for 7 modules
- [x] CLAUDE.md — AI config optimized for OpenCode
- [x] .claude/agents/ — 5 sub-agents
- [x] .claude/rules/ — 4 rules
- [x] .claude/skills/ — 2 skills
- [x] Infrastructure — docker-compose, Dockerfiles, .env.example, alembic

### M1: Auth & Tenants — Backend (100%)
- [x] Models: Tenant, User (with tenant_id FK, indexes)
- [x] Core: config.py, security.py (bcrypt + JWT), database.py (async), dependencies.py
- [x] Schemas: all Request + Response Pydantic models
- [x] Services: auth_service.py (register, login, refresh, profile, invite, roles, remove)
- [x] API routes: auth.py (5 endpoints) + tenants.py (4 endpoints) = 9 endpoints total

### M1: Auth & Tenants — Frontend (100%)
- [x] api/client.js (axios + JWT interceptor + auto-refresh)
- [x] AuthContext.jsx (useReducer, login/register/logout)
- [x] LoginPage.jsx, RegisterPage.jsx (forms with error/loading states)
- [x] Layout.jsx (sidebar nav + user section + Outlet)
- [x] ProtectedRoute.jsx (auth guard)
- [x] App.jsx (BrowserRouter, routes, placeholder pages for M2-M6)

### M1: Auth & Tenants — Tests (WRITTEN, NOT RUN)
- [x] requirements.txt — added pytest, pytest-asyncio, aiosqlite, email-validator
- [x] pyproject.toml — pytest config (asyncio_mode = "auto")
- [x] tests/conftest.py — async fixtures (SQLite in-memory, test client, auth helpers)
- [x] tests/test_auth.py — 15 tests (register, login, refresh, me, update_me + edge cases)
- [x] tests/test_tenants.py — 14 tests (list_users, invite, update_role, remove + RBAC + isolation)
- [ ] **BLOCKED: Python not installed locally, Docker not running. Need Python 3.11+ to run tests.**

## Next Steps (in order)

1. **Install Python 3.11+** (or start Docker Desktop)
2. **Run M1 tests**: `cd backend && pip install -r requirements.txt && pytest -v`
3. **Fix any test failures**
4. **M2: Workflow CRUD — Backend** (models → schemas → services → routes → migration)
   - Read M2 section in TECH_SPEC.md first
   - Read .claude/agents/backend-engineer.md for patterns
5. **M2: Workflow CRUD — Frontend** (api → hooks → components → pages)
6. **M2: Tests**
7. **M5: Tool Registry** (Backend + Frontend + Tests)
8. **M3: Builder UI** (React Flow canvas, drag-and-drop, agent config)
9. **M4: Execution Engine** (LangGraph compiler, executor, WebSocket)
10. **M6: Dashboard** (KPI, cost timeline, export)
11. **M7: Infrastructure** (final Docker, Alembic migrations, env config)

## Module Implementation Order
M1 (Auth) → M2 (Workflow CRUD) → M5 (Tool Registry) → M3 (Builder UI) → M4 (Execution Engine) → M6 (Dashboard) → M7 (Infrastructure)

## Commands to Resume
```bash
# Install Python deps & run tests
cd backend
pip install -r requirements.txt
pytest -v

# Frontend dev
cd frontend
npm install
npm run dev

# Full stack (Docker)
docker-compose up
```
