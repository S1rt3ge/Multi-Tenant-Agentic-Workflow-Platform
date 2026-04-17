# Changelog

All notable changes to this project should be documented in this file.

The format is based on Keep a Changelog and the project currently follows a simple semantic versioning approach.

## [0.1.3] - 2026-04-17

### Fixed

- Published `graphpilot` package now carries the corrected `v*` GHCR image tag defaults, restoring the real install-and-run path for released npm artifacts

### Changed

- Formalized release acceptance with `V0_1_3_CHECKLIST.md`
- Added cross-platform CLI sanity tracking and CI packaging/init validation for Linux, Windows, and macOS

## [0.1.2] - 2026-04-16

### Fixed

- Secured execution streaming by enforcing WebSocket authentication and tenant-scoped execution ownership checks
- Enforced role-based execution start permissions (`owner`/`editor`) and tightened execution list pagination bounds
- Hardened API tool handling with SSRF protections for private/local networks and safer secret-preserving tool update merges
- Improved execution lifecycle resilience for cancellation races, terminal event emission, and cyclic workflow routing behavior
- Normalized auth emails to lowercase for case-insensitive registration/login/invite consistency
- Stabilized frontend execution/builder flows (save-before-run, error handling, completion refresh) and viewer-safe action gating
- Hardened CLI/runtime defaults with generated local JWT secrets, pinned image tags, and conflict-resistant local smoke DB port handling

### Changed

- Frontend runtime image now runs as non-root (`nginx`) user
- Deploy preflight workflow now restricts secret-backed runs to version tags (`v*`) by default

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
