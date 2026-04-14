# Multi-Tenant Agentic Workflow Platform

[![CI](https://github.com/S1rt3ge/Multi-Tenant-Agentic-Workflow-Platform/actions/workflows/ci.yml/badge.svg)](https://github.com/S1rt3ge/Multi-Tenant-Agentic-Workflow-Platform/actions/workflows/ci.yml)
[![Smoke](https://github.com/S1rt3ge/Multi-Tenant-Agentic-Workflow-Platform/actions/workflows/smoke.yml/badge.svg)](https://github.com/S1rt3ge/Multi-Tenant-Agentic-Workflow-Platform/actions/workflows/smoke.yml)

No-code platform for designing, running, and monitoring multi-tenant agent workflows on top of LangGraph.

## Status

- Project status: complete
- Modules implemented: M1, M2, M5, M3, M4, M6, M7
- Backend test suite: `247 passing tests`
- Frontend build stack: Vite
- Frontend dependency audit: `0 vulnerabilities` in clean Docker environment
- CI: GitHub Actions for backend tests, frontend build, and backend compose smoke flow

## Stack

- Backend: FastAPI, SQLAlchemy Async, PostgreSQL, Alembic, LangGraph
- Frontend: React (JavaScript only), React Flow, Tailwind CSS, Recharts
- Infrastructure: Docker, docker-compose, Nginx
- Auth: JWT access/refresh tokens, bcrypt

## Implemented Modules

1. M1 Auth & Tenants
2. M2 Workflow CRUD
3. M5 Tool Registry
4. M3 Builder UI
5. M4 Execution Engine
6. M6 Dashboard & Analytics
7. M7 Infrastructure

## Key Features

- Multi-tenant SaaS architecture with tenant-scoped data isolation
- Visual workflow builder with React Flow
- Agent configuration per workflow node
- Tool registry for API, database, and file-system tools
- LangGraph-based execution engine with live logs and cost tracking
- Analytics dashboard with KPI, cost timeline, workflow breakdown, and export
- Dockerized local and production environments
- Health checks, tenant middleware, and rate limiting
- Structured request logging with request IDs for correlation
- Compose-based smoke coverage across auth, workflows, tools, executions, and analytics

## Project Structure

```text
backend/
  app/
    api/v1/
    core/
    engine/
    middleware/
    models/
    schemas/
    services/
  tests/
frontend/
  src/
    api/
    components/
    hooks/
    pages/
```

## Run Locally

### Full stack with Docker

```bash
docker-compose up
```

This runs:
- PostgreSQL 16
- FastAPI backend with auto-reload
- Vite frontend dev server on `http://localhost:3000`

### Backend only

```bash
docker build --no-cache -t agentic-backend ./backend
docker run --rm agentic-backend python -m pytest -p no:cacheprovider tests/ -v
```

### Frontend only

```bash
cd frontend
npm install
npm run dev
```

## Production Compose

```bash
docker-compose -f docker-compose.prod.yml up --build -d
```

## Tests

Run full backend suite:

```bash
docker build --no-cache -t agentic-backend ./backend
docker run --rm agentic-backend python -m pytest -p no:cacheprovider tests/ -v
```

Current result:

```text
247 passed
```

## Smoke Check

Local backend smoke flow via Docker Compose:

```powershell
./scripts/smoke-backend.ps1
```

This validates a critical path end-to-end:
- database startup
- backend startup and `/health`
- auth register
- auth login
- authenticated `/api/v1/auth/me`
- workflow create/list/detail/delete
- tool create/list/update/delete
- execution start/list/detail/logs/cancel
- analytics overview/timeline/breakdown/export

## Important Notes

- Frontend is JavaScript-only. No TypeScript files are used.
- Backend is async-first: FastAPI `async def`, `AsyncSession`, async services.
- All API routes are versioned under `/api/v1/`.
- Tenant isolation is enforced at the ORM/service layer with `tenant_id` filtering.

## Main Docs

- `TECH_SPEC.md` — full product specification
- `PROGRESS.md` — implementation progress and latest test totals
- `PROJECT_IDEA.md` — product rationale, market, and architecture
- `DEPLOYMENT.md` — production deployment steps, required env, and post-deploy checks
- `CHANGELOG.md` — release history
- `RELEASE.md` — lightweight release checklist and tagging flow

## Automation

- `CI` workflow: backend Docker tests + frontend build
- `Smoke` workflow: compose-backed backend smoke path
- `Release` workflow: validates tag/version/changelog alignment and creates GitHub Releases for `v*` tags
- `Deploy` workflow: manual deployment preflight for refs/tags with required secrets/vars validation
- `Publish Images` workflow: builds and pushes backend/frontend images to GHCR on `main` and release tags
- `Publish CLI` workflow: publishes the `graphpilot` npm package on version tags

## Local CLI

The repository now includes a local launcher CLI package under `cli/` with the working name `graphpilot`.

Intended usage model:

```bash
npm install -g ./cli
graphpilot init
graphpilot doctor
graphpilot up
graphpilot status
```

Current commands:

- `graphpilot init` — creates the local runtime directory and default stack files under `~/.graphpilot`
- `graphpilot doctor` — checks Docker/Compose and whether GraphPilot has been initialized locally
- `graphpilot up` — starts the local stack from the initialized runtime directory
- `graphpilot status` — shows the local Docker Compose service status
- `graphpilot down` — stops the local stack
- `graphpilot reset` — stops the local stack and removes local Docker volumes
- `graphpilot logs` — follows compose logs
- `graphpilot smoke` — reserved for a future packaged smoke flow

Current packaging status:

- CLI packaging layer exists
- local runtime initialization exists
- packaged runtime uses GHCR-published backend/frontend images

Recommended happy path:

```bash
npm install -g ./cli
graphpilot init
graphpilot up
graphpilot status
```

Windows note:

- if PowerShell blocks the generated `graphpilot.ps1` shim, use `graphpilot.cmd` instead
- Docker Desktop (or another local Docker daemon) must be running before `graphpilot up`
