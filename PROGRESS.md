# Project Progress Tracker
# Last updated: 2026-04-17

## Purpose

This document is the operational snapshot for the repository.

Use it for:

- latest workflow and release health
- current test totals
- implemented module inventory
- notable post-spec/platform hardening work

Use other docs for procedures:

- `RELEASE.md` for release steps
- `DEPLOYMENT.md` for deployment steps
- `ROLLBACK.md` for rollback/restore

## Current Status: PROJECT COMPLETE — All 7 Modules Implemented ✅

## Current Operational State

- Release baseline `v0.1.2` (2026-04-16):
  - `CI` (main): run `24503132147` — success
  - `Smoke` (main): run `24503132175` — success
  - `Release` (tag): run `24503137007` — success
  - `Publish Images` (tag): run `24503136993` — success
  - `Publish CLI` (tag): run `24503137010` — success
  - GitHub Release: `https://github.com/S1rt3ge/Multi-Tenant-Agentic-Workflow-Platform/releases/tag/v0.1.2`
  - npm: `graphpilot@0.1.2` (`latest`)
- GHCR: `ghcr.io/s1rt3ge/graphpilot-backend:v0.1.2`, `ghcr.io/s1rt3ge/graphpilot-frontend:v0.1.2`
- Current pipeline state on `main`:
  - `CI` — green
  - `Smoke` — green
  - `CLI E2E` — green
  - `Observability SLO` — green
  - `Publish Images` — green
  - `Security Gates` — green

- Backend test suite: **267 passing tests**
- Frontend build stack: **Vite**
- Frontend dependency audit: **0 vulnerabilities** in clean Docker environment
- CI workflows:
  - `CI` — backend Docker tests + frontend build
  - `Smoke` — compose-backed auth/workflow/tool/execution/analytics path
- `CLI E2E` — npm-installed graphpilot runtime check + packaged smoke command
  - `Release` — tag-based release validation and GitHub Release creation
  - `Release Health Check` — verifies released GHCR backend/frontend images boot and respond after release publication
  - `Deploy` — manual deployment preflight with required secret/variable validation
  - `Publish Images` — GHCR publication for backend/frontend runtime images on main and release tags
  - `Publish CLI` — npm publication for the `graphpilot` package on release tags
  - `Observability SLO` — validates `/health` and `/ready` status/latency thresholds on compose runtime
  - `Security Gates` — CodeQL SAST, Gitleaks secret scan, dependency/license audit, and backend container vulnerability scan
- Observability: structured request logging with `X-Request-ID` correlation
  - Workflow heartbeat JSON lines emitted by CI/Smoke/Release/Publish/ReleaseHealth/SLO flows for external monitoring hooks
  - baseline SLO script available at `scripts/check-api-slo.py` (default thresholds: `/health <= 1000ms`, `/ready <= 1500ms`)
- Security gates:
  - CodeQL SAST + Gitleaks + dependency/license audit + backend image SARIF scanning
  - deterministic `results.sarif` upload plus explicit SARIF-based container vulnerability gate after scan upload
  - temporary accepted image risks are tracked in `.security/container-risk-accepted.json` with expiry/owner instead of being silently ignored
- Recovery operations:
  - `ROLLBACK.md` now defines production/local rollback, SQL backup, restore, and post-incident validation flow
- Dev compose: Vite frontend dev server + backend auto-reload + PostgreSQL
- Deployment docs: production deployment guide with required env and post-deploy checks
- Release process: centralized backend version constant, changelog, and release checklist
- Local packaging: `graphpilot` CLI with initialized user app directory, runtime templates, and local stack UX commands (`status`, `reset`)

## Module Implementation Order
M1 (Auth) → M2 (Workflow CRUD) → M5 (Tool Registry) → M3 (Builder UI) → M4 (Execution Engine) → M6 (Dashboard) → M7 (Infrastructure)

## Completed Modules

### M1: Auth & Tenants ✅ (commit `3f55d05`)
- **Backend**: 5 auth endpoints (register, login, refresh, me, update profile) + 4 tenant endpoints (list users, invite, update role, remove)
- **Models**: Tenant + User with UUID PKs, RBAC (owner/editor/viewer)
- **Services**: auth_service.py with JWT tokens, bcrypt, selectinload
- **Schemas**: 12 Pydantic models
- **Tests**: 38 tests (19 auth + 19 tenants)
- **Migration**: `0001_m1_auth_tenants`
- **Frontend**: LoginPage, RegisterPage, AuthContext, axios JWT interceptor, ProtectedRoute, Layout

### M2: Workflow CRUD ✅ (commit `683b7d3`)
- **Backend**: 6 endpoints (create, list paginated+search, get, update, duplicate, soft-delete)
- **Model**: Workflow with JSONB `definition`, `execution_pattern` (linear/parallel/cyclic), soft delete via `is_active`
- **Business logic**: tenant `max_workflows` limit check, `(Copy)` suffix on duplicate, full definition replace
- **Tests**: 38 workflow tests after post-spec fixes (76 total with M1)
- **Migration**: `0002_m2_workflows`
- **Frontend**: WorkflowListPage (card grid, search 300ms debounce, pagination, 4 states), CreateWorkflowModal, WorkflowCard, useWorkflows hook

### M5: Tool Registry ✅ (commit `916d5de`)
- **Backend**: ToolRegistry model (JSONB config, tool_type: api|database|file_system, composite unique tenant_id+name)
- **Endpoints**: POST create, GET list, PUT update, DELETE (soft-delete), POST test
- **Features**: Config validation per type, secret masking on GET, real HTTP test via httpx (10s timeout)
- **Tests**: 42 tests — all 115 passed (M1: 38 + M2: 35 + M5: 42)
- **Migration**: `0003_m5_tool_registry`
- **Frontend**: ToolsPage (4 states), CreateToolModal (dynamic config forms per type), ToolCard, useTools hook, tools.js API client

### M3: Builder UI ✅ (commit `90a8825`)
- **Backend**: AgentConfig model (JSONB tools, role: retriever|analyzer|validator|escalator|custom, model selection, memory_type, composite unique workflow_id+node_id)
- **Endpoints**: GET list, POST create, PUT update, DELETE under `/api/v1/workflows/{wf_id}/agents`
- **Service**: Agent service with tenant isolation, max_agents_per_workflow limit, field validation
- **Tests**: 32 agent tests — all 147 passed (M1: 38 + M2: 35 + M5: 42 + M3: 32)
- **Migration**: `0004_m3_agent_configs`
- **Frontend**: Full React Flow visual editor with AgentNode, Sidebar, Canvas, AgentConfigPanel, Toolbar, useBuilder hook, BuilderPage

### M4: Execution Engine ✅
- **Backend**:
  - Models: Execution (status lifecycle, JSONB input/output, cost tracking) + ExecutionLog (step details, tokens, cost, reasoning)
  - Engine: cost.py (per-model pricing), compiler.py (JSON → LangGraph StateGraph), executor.py (full lifecycle orchestrator), agents/base.py (LLM call with retry/timeout), tools/executor.py (API/DB/FS tool execution)
  - Service: execution_service.py (create, list paginated, get, get logs, cancel)
  - API: POST execute, GET list, GET detail, GET logs, POST cancel, WS stream
  - Tests: 51 tests after post-spec fixes — all 201 passed (M1: 38 + M2: 38 + M5: 42 + M3: 32 + M4: 51)
  - Migration: `0005_m4_executions`
- **Frontend**:
  - API client: executions.js (start, list, get, logs, cancel, WS URL)
  - Hook: useExecution.js (execution state + WebSocket streaming)
  - Components: RunPanel.jsx (input form + Run/Cancel + progress), LogViewer.jsx (timeline, expandable, filterable), ReadOnlyCanvas.jsx (read-only graph with active node highlighting)
  - Page: ExecutionPage.jsx (split view: canvas left + logs right)
  - Routes: `/workflows/:id/execute` (new) and `/workflows/:id/execute/:executionId` (view existing)
  - Builder integration: handleRun validates graph and navigates to ExecutionPage

### M6: Dashboard & Analytics ✅
- **Backend**:
  - No new models — pure SQL aggregation from `executions` and `workflows`
  - Schemas: OverviewResponse, CostTimelineItem, WorkflowBreakdownItem, ExportRow
  - Service: analytics_service.py (overview KPI, cost timeline with zero-fill, workflow breakdown with avg duration, CSV/JSON export, 60s in-memory cache with per-tenant invalidation)
  - API: 4 GET endpoints (overview, cost-timeline, workflow-breakdown, export)
  - Tests: 27 tests — all 222 passed (M1: 38 + M2: 35 + M5: 42 + M3: 32 + M4: 48 + M6: 27)
- **Frontend**:
  - API client: analytics.js (fetchOverview, fetchCostTimeline, fetchWorkflowBreakdown, exportData with CSV download)
  - Hook: useDashboard.js (auto-refresh 60s, period/days selectors, parallel data loading)
  - Components: MetricsGrid.jsx (4 KPI cards with progress bars), CostChart.jsx (Recharts line chart with budget reference line), WorkflowBreakdown.jsx (sortable table with cost % bars)
  - Page: DashboardPage.jsx (4 UI states: loading/loaded/empty/error, period selector, export controls)
  - App.jsx updated: replaced placeholder with real DashboardPage import

### M7: Infrastructure ✅
- **Middleware**:
  - TenantMiddleware: JWT extraction, `User.is_active` verification, `request.state.tenant_id` + `request.state.user_id` injection, public path bypass, OPTIONS/WebSocket passthrough
  - RateLimitMiddleware: in-memory sliding window, 100 req/min per tenant (or per IP for unauthenticated), X-RateLimit-* response headers, only `/api/` paths
- **Health endpoints**: `/health` (liveness — version, env, status) and `/ready` (readiness — DB connectivity check via DI)
- **CORS**: updated to expose rate limit headers (X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset)
- **Docker — Backend**: multi-stage Dockerfile (deps + runtime), non-root `appuser`, libpq5 runtime only, healthcheck
- **Docker — Frontend**: multi-stage Dockerfile (node build → nginx:1.25-alpine), non-root nginx, healthcheck
- **Nginx**: gzip, static cache 1y, `/api/` proxy to backend, `/ws/` WebSocket proxy, SPA fallback, security headers (X-Frame-Options, X-Content-Type-Options, X-XSS-Protection)
- **Docker Compose (dev)**: `docker-compose.yml` — PostgreSQL 16 with healthcheck, backend with volume mount + --reload, frontend Vite dev server via `node:20-alpine`
- **Docker Compose (prod)**: `docker-compose.prod.yml` — internal network isolation, 4 uvicorn workers, resource limits (CPU/memory), no DB port exposure, build args
- **Environment**: `.env.example` with all documented vars (DATABASE_URL, JWT_SECRET, JWT_ACCESS/REFRESH expiry, OPENAI/ANTHROPIC keys, APP_ENV, CORS_ORIGINS, VITE_API_URL)
- **Tests**: 19 infrastructure tests after post-spec fixes (health: 4, tenant middleware: 6, rate limiting: 5, CORS: 2, config: 2) — all 247 passed

## Post-Spec Fixes

After the initial 7-module completion, several spec-aligned backend gaps were closed:

- **Concurrent execution limits by plan** (`fix(M4)` commit `8b541da`)
  - Enforced active execution caps per tenant plan: `free=1`, `pro=5`, `team=20`
  - Counts only `pending` and `running` executions toward the limit
  - Added execution tests for free/pro concurrency behavior and completed-slot reuse
- **Workflow delete guard for active executions** (`fix(M2)` commit `310ce8f`)
  - Soft-delete now returns `409` if a workflow has `pending` or `running` executions
  - Completed executions no longer block deletion
  - Added workflow API tests for pending/running/completed execution delete cases
- **TenantMiddleware active-user validation** (`fix(M7)` commit `456bbb0`)
  - Middleware now verifies `User.is_active` before injecting tenant context
  - Middleware DB access is routed through `app.state.db_session_factory` for test/prod compatibility
  - Added infrastructure coverage for deactivated users
- **Frontend build migration from CRA to Vite** (`refactor(frontend)` commit `b087fc7`)
  - Replaced legacy `react-scripts` toolchain with Vite
  - Switched frontend env variables from `REACT_APP_*` to `VITE_*`
  - Updated frontend Docker build output from `build/` to `dist/`
  - Reduced frontend dependency surface and enabled follow-up cleanup to 0 frontend audit issues
- **Observability + request correlation** (`feat(observability)` commit `9858865`)
  - Added structured request logging with `json`/`text` formatter support
  - Added `X-Request-ID` generation and propagation for request correlation
  - Logged method, path, status, duration, tenant, user, and client IP per request
- **Compose smoke coverage** (`test(smoke)` commits `0b32047`, `8ae4a3c`, `7097105`, `e1aca6d`, `7ab1d99`)
  - Added GitHub Actions smoke workflow for compose-backed backend startup
  - Covered auth, workflow CRUD, tool CRUD, execution lifecycle, and analytics endpoints
  - Added matching local script: `scripts/smoke-backend.ps1`
- **Frontend production hardening** (multiple commits)
  - Same-origin API/WebSocket defaults instead of localhost fallbacks
  - Conservative CSP and stronger nginx security headers
  - Route-level lazy loading and Vite manual chunk splitting
  - Upgraded Vite toolchain to remove remaining frontend audit issues

## All Modules Complete

No remaining modules. The platform is feature-complete per TECH_SPEC.md.

## Test Summary
| Module | Tests | Status |
|--------|-------|--------|
| M1 Auth | 38 | ✅ Pass |
| M2 Workflows | 38 | ✅ Pass |
| M5 Tools | 44 | ✅ Pass |
| M3 Agents | 32 | ✅ Pass |
| M4 Executions | 60 | ✅ Pass |
| M6 Analytics | 27 | ✅ Pass |
| M7 Infrastructure | 19 | ✅ Pass |
| **Total** | **267** | **✅ All Pass** |

## Commands
```bash
# Backend tests (via Docker)
docker build --no-cache -t agentic-backend ./backend
docker run --rm agentic-backend python -m pytest -p no:cacheprovider tests/ -v

# Frontend dev
cd frontend && npm install && npm run dev

# Full stack — development (Docker)
docker-compose up

# Full stack — production (Docker)
docker-compose -f docker-compose.prod.yml up --build -d

# Alembic migrations
alembic upgrade head
```
