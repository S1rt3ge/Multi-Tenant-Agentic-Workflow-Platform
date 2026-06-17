# M9 Closure Report: Connector Runtime and Trigger System

Date: 2026-05-15
Status: closed

## Summary

M9 added the first production integration vertical slice for GraphPilot:

- built-in HTTP connector manifest;
- tenant-scoped encrypted connector credentials;
- redacted credential previews and API responses;
- workflow webhook triggers;
- public webhook ingestion and webhook event audit records;
- connector node execution inside the workflow executor;
- connector-specific execution log metadata;
- SSRF/private-network protection for HTTP connector requests;
- sanitized connector errors and output previews;
- Workflow Doctor detector for missing connector credentials;
- frontend API helpers for connector and trigger APIs.

This moves the platform from agent-only graph execution toward an automation platform foundation comparable to n8n-style integrations, while keeping the first connector slice narrow and testable.

## Implementation Artifacts

Backend:

- `backend/alembic/versions/0009_m9_connector_runtime.py`
- `backend/app/models/connector.py`
- `backend/app/schemas/connector.py`
- `backend/app/api/v1/connectors.py`
- `backend/app/services/connector_security.py`
- `backend/app/services/connector_service.py`
- `backend/app/services/connector_runtime_service.py`
- connector branch in `backend/app/engine/executor.py`
- connector-aware compilation in `backend/app/engine/compiler.py`
- connector metadata in `backend/app/models/execution.py`
- connector metadata in `backend/app/schemas/execution.py`
- Workflow Doctor missing credential detector in `backend/app/services/workflow_doctor_service.py`

Frontend:

- `frontend/src/api/connectors.js`
- `frontend/src/api/connectors.test.js`

Tests:

- `backend/tests/test_connector_runtime.py`
- existing Workflow Doctor and execution tests remained green.

Docs:

- `docs/M9_CONNECTOR_RUNTIME_SPEC.md`
- `docs/build-configs/M9_CONNECTOR_RUNTIME.yaml`
- `docs/M9_TDD_START_CHECKLIST.md`
- `docs/M9_ACCEPTANCE_GATE.md`

## Verification

Automated checks:

- `python -m pytest tests/test_connector_runtime.py -q`: `11 passed`
- `python -m pytest -q`: `298 passed`
- `python -m ruff check app tests alembic`: passed
- `npm test`: `14 passed`
- `npm run build`: passed
- `npm audit --audit-level=high`: `0 vulnerabilities`

Migration:

- `python -m alembic upgrade head`: passed against local Postgres on `localhost:55432`.

Manual acceptance smoke:

- passed against local backend `http://127.0.0.1:8001` and frontend `http://127.0.0.1:3000`.

## Security Review Notes

- Raw credential config is encrypted before persistence.
- API responses expose only `config_preview`, never `config` or `encrypted_config`.
- Credential previews mask secret values.
- Connector request headers, response headers, webhook headers, and error strings are sanitized.
- HTTP connector blocks localhost, private, link-local, reserved, multicast, and non-HTTP targets.
- HTTP connector does not follow redirects in M9.
- Credential, trigger, and event access is tenant-scoped except public webhook resolution by opaque id.
- Public webhook ids are generated with high-entropy URL-safe tokens.

## Risks And Follow-Ups

- Public webhook auth should be upgraded with signed headers or shared-secret validation in a policy milestone.
- Webhook-created pending executions need queue/worker semantics in a runtime milestone.
- Connector response body redaction is best effort; future typed contracts should mark secret output fields explicitly.
- Credential encryption currently derives from `CREDENTIAL_ENCRYPTION_KEY` or `JWT_SECRET`; production deployments should set a dedicated credential key.
- Connector UX is not implemented yet; M10 owns making M9 usable from the builder.

## Next Milestone

M10 should implement Connector UX and Builder integration:

- credential manager;
- connector node palette item;
- HTTP request config panel;
- credential picker;
- webhook trigger panel;
- execution log connector display;
- Doctor action path from missing credential diagnosis to credential creation/selection.
