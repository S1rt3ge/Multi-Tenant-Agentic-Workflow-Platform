# Changelog

All notable changes to this project should be documented in this file.

The format is based on Keep a Changelog and the project currently follows a simple semantic versioning approach.

## [0.1.1] - 2026-04-15

### Fixed

- Packaged backend runtime startup now exports `PYTHONPATH=/app`, fixing `graphpilot up` failures where Alembic could not import the `app` package during container boot

## [0.1.0] - 2026-04-14

### Added

- Full implementation of the multi-tenant agentic workflow platform across M1, M2, M5, M3, M4, M6, and M7
- FastAPI backend with async SQLAlchemy, JWT auth, RBAC, tenant isolation, workflow/tool/agent/execution/analytics APIs
- React frontend with workflow builder, execution UI, dashboard analytics, auth flows, and tool registry
- Dockerized development and production environments
- GitHub Actions CI and compose-backed smoke workflow
- Structured request logging with request correlation IDs
- Execution lifecycle logging and improved production deployment docs

### Changed

- Frontend migrated from CRA/react-scripts to Vite
- Frontend bundle split into lazy route and vendor chunks
- Frontend dependency audit reduced to zero vulnerabilities in clean Docker environment
- Production nginx hardened with CSP and additional security headers

### Fixed

- Concurrent execution limits enforced by tenant plan
- Workflow deletion blocked when active executions exist
- Tenant middleware validates active users
- Analytics cache invalidated when new executions are created
- Production readiness endpoint exposed through nginx proxy
