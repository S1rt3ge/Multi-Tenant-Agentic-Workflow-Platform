# Multi-Tenant Agentic Workflow Platform

[![CI](https://github.com/S1rt3ge/Multi-Tenant-Agentic-Workflow-Platform/actions/workflows/ci.yml/badge.svg)](https://github.com/S1rt3ge/Multi-Tenant-Agentic-Workflow-Platform/actions/workflows/ci.yml)
[![Smoke](https://github.com/S1rt3ge/Multi-Tenant-Agentic-Workflow-Platform/actions/workflows/smoke.yml/badge.svg)](https://github.com/S1rt3ge/Multi-Tenant-Agentic-Workflow-Platform/actions/workflows/smoke.yml)

Production-oriented platform for designing, executing, and monitoring multi-tenant AI agent workflows with visual graph authoring, tenant isolation, execution tracing, cost awareness, and self-hosted runtime distribution.

## Overview

This project was built as a full-stack, end-to-end implementation of a multi-tenant agent workflow system.

It combines:

- visual workflow authoring
- configurable agent nodes and tool integrations
- graph-based execution orchestration
- tenant-aware auth and RBAC
- execution logging and analytics
- operational hardening for release, rollback, and self-hosted distribution

The result is not just a prototype UI. It is a releaseable system with CI/CD, smoke coverage, security gates, rollback guidance, cross-platform CLI validation, and published runtime artifacts.

## Product Capabilities

- Multi-tenant workspace model with tenant-scoped data isolation
- JWT auth with access/refresh flow and role-based permissions (`owner`, `editor`, `viewer`)
- Visual workflow builder powered by React Flow
- Per-node agent configuration for role, prompt, model, tools, and execution behavior
- Tool registry for external API, database, and file-oriented integrations
- LangGraph-backed execution engine with support for linear and cyclic workflow patterns
- Execution lifecycle tracking with logs, cancellation, and status transitions
- Analytics views for KPI, cost, execution history, and export
- Self-hosted local runtime via the published `graphpilot` CLI

## Architecture

### Backend

- FastAPI
- async SQLAlchemy + PostgreSQL
- Alembic migrations
- LangGraph-based orchestration
- tenant middleware, request logging, and rate limiting

Key responsibilities:

- auth and tenant management
- workflow CRUD and graph persistence
- agent/tool configuration
- execution orchestration and runtime logging
- analytics aggregation and export
- health/readiness infrastructure endpoints

### Frontend

- React (JavaScript)
- React Flow
- Tailwind CSS
- Recharts

Key responsibilities:

- authentication flows
- workflow list and duplication/deletion UX
- visual graph builder
- execution monitoring UI
- analytics dashboard
- team management and invited-user onboarding

### Runtime and Delivery

- Docker / Docker Compose
- Nginx for frontend serving
- GitHub Actions for CI/CD
- GHCR for runtime images
- npm for CLI distribution

## Engineering Highlights

- Async-first backend architecture with explicit tenant scoping in service/data access paths
- Structured request/execution logging with correlation-friendly operational design
- Real release pipeline with GitHub Releases, GHCR images, and published npm CLI package
- Security workflow including CodeQL, secret scanning, dependency audit, and image scanning
- Compose-based smoke tests that exercise auth, workflows, tools, executions, and analytics
- Dedicated rollback and restore runbook
- Cross-platform CLI sanity coverage across Linux, Windows, and macOS
- Corrective release work to validate the actual published artifact path, not only repo-local behavior

## Key Technical Decisions

### Multi-tenant isolation as a first-class concern

Tenant context is carried through the backend stack and enforced in service/data access paths rather than being treated as a UI-only concept. That keeps authorization, workflow access, execution history, and analytics scoped consistently.

### Graph execution built around orchestration, not just CRUD

The system does more than store workflows as JSON. Workflow definitions are compiled into executable runtime structures, executed through a graph-oriented engine, and exposed back to the user through execution state, logs, and analytics.

### Operational maturity treated as part of the product

This project was intentionally pushed beyond “feature-complete” into release-readiness:

- release/version validation
- published runtime images
- distributed CLI runtime
- rollback and restore runbooks
- security scanning and SLO checks
- cross-platform CLI validation

### Published artifact validation over local-only confidence

One of the most important parts of the work was validating the actual released artifacts, not just the repository state. That surfaced and fixed real issues in the npm-distributed CLI/runtime path that would not have been caught by source-only verification.

## Why This Project Is Interesting

This project sits at the intersection of several difficult engineering concerns:

- product UX for graph-based systems
- multi-tenant backend correctness
- AI workflow orchestration
- observability and execution traceability
- secure release engineering
- packaging a self-hosted developer-facing runtime

It is intentionally broad: it demonstrates the ability to take a complex idea from architecture and specification through implementation, hardening, release automation, and real artifact validation.

## Repository Structure

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
    context/
    hooks/
    pages/

cli/
  bin/
  templates/
```

## Core Workflows

### 1. Tenant and User Management

- register a tenant
- authenticate users
- invite team members
- enforce role restrictions
- require password reset for invited users on first access

### 2. Workflow Authoring

- create and duplicate workflows
- model workflows as node/edge graphs
- configure agent nodes independently
- validate graph structure before execution

### 3. Execution

- compile saved workflow definitions into executable runtime structures
- start, inspect, and cancel executions
- stream execution progress
- track token usage and cost-related metrics

### 4. Monitoring and Analytics

- inspect execution state and logs
- view aggregate analytics
- export analytics data
- monitor runtime health/readiness

## Local Development

### Full stack

```bash
docker-compose up
```

### Backend test suite

```bash
docker build --no-cache -t agentic-backend ./backend
docker run --rm agentic-backend python -m pytest -p no:cacheprovider tests/ -v
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## Self-Hosted CLI Runtime

The repository includes a distributable CLI package: `graphpilot`.

Typical local runtime flow:

```bash
npm install -g graphpilot
graphpilot init
graphpilot doctor
graphpilot up
graphpilot status
graphpilot smoke
graphpilot down
```

CLI features:

- initializes a local runtime directory
- uses published backend/frontend runtime images
- runs packaged smoke validation
- handles common local port conflicts more gracefully

Windows note:

- if PowerShell blocks the generated shim, use `graphpilot.cmd`

## Quality and Delivery

This repository is set up as a releaseable engineering project, not just an application code dump.

Current automation includes:

- CI
- backend smoke flow
- npm-installed CLI end-to-end path
- cross-platform CLI sanity
- release health verification
- observability SLO checks
- security gates
- image publication
- CLI publication

## What This Project Demonstrates

This project demonstrates capability across multiple engineering layers:

- full-stack product development
- multi-tenant backend design
- graph-based execution systems
- frontend builder UX for complex domain models
- operational hardening and release engineering
- security-minded pipeline design
- packaging and distribution of self-hosted developer tooling

For a hiring context, the strongest signal is not any single framework choice. It is the ability to carry a technically complex system all the way to a release-quality state: feature implementation, runtime reliability, CI/CD discipline, security review, rollback planning, and artifact-level validation.

## Documentation

- `TECH_SPEC.md` — technical product specification
- `PROJECT_IDEA.md` — original problem framing and solution rationale
- `PROGRESS.md` — current operational snapshot
- `DEPLOYMENT.md` — deployment guidance
- `ROLLBACK.md` — rollback and restore runbook
- `CROSS_PLATFORM.md` — platform validation matrix
- `V0_1_3_CHECKLIST.md` — release acceptance checklist
- `CHANGELOG.md` — release history
- `RELEASE.md` — release process

## Notes

- Frontend code is intentionally JavaScript-based rather than TypeScript-based
- The project favors small operationally-correct changes over speculative abstraction
- Several release-hardening fixes were validated against published artifacts, not only against local source state
