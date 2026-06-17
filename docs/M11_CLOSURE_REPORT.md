# M11 Closure Report: Durable Webhook Dispatch Pipeline

Date: 2026-05-16
Status: complete

## Outcome

M11 turns webhook ingestion from a passive `pending` execution handoff into a durable internal dispatch pipeline:

- public webhook ingestion still creates pending executions;
- an internal dispatcher can run eligible webhook executions through the existing executor;
- an optional process worker can poll and dispatch when enabled;
- retry/backoff/dead-letter metadata is stored on execution input data;
- the builder connector workspace now exposes queue observability without rendering webhook payloads or headers.

## Changed Areas

Backend:

- `backend/app/services/webhook_dispatcher_service.py`
- `backend/app/services/webhook_dispatcher_worker.py`
- `backend/app/core/config.py`
- `backend/app/main.py`
- `backend/tests/test_webhook_dispatcher.py`
- `backend/tests/test_webhook_dispatcher_worker.py`

Frontend:

- `frontend/src/api/executions.js`
- `frontend/src/api/executions.test.js`
- `frontend/src/components/connectors/DispatchQueuePanel.jsx`
- `frontend/src/components/connectors/DispatchQueuePanel.test.jsx`
- `frontend/src/components/connectors/ConnectorWorkspacePanel.jsx`
- `frontend/src/components/connectors/ConnectorWorkspacePanel.test.jsx`
- `frontend/src/hooks/useBuilder.js`
- `frontend/src/pages/BuilderPage.jsx`

Docs:

- `docs/M11_WEBHOOK_DISPATCHER_IDEA.md`
- `docs/M11_WEBHOOK_DISPATCHER_SPEC.md`
- `docs/M11_TDD_START_CHECKLIST.md`
- `docs/M11_PROGRESS.md`
- `docs/build-configs/M11_WEBHOOK_DISPATCHER.yaml`

## Acceptance Result

- Pending webhook executions dispatch through the existing executor.
- Non-webhook pending executions are skipped.
- Batch limits are respected.
- Worker settings default to disabled.
- Worker lifecycle is installed only when `WEBHOOK_DISPATCHER_ENABLED=true`.
- Retryable failures schedule a new pending retry execution.
- Future retry attempts are deferred.
- Exhausted retryable attempts are marked dead-lettered.
- Connector workspace shows recent webhook dispatch queue state.
- Queue UI does not render webhook payloads or headers.

## Verification

- `python -m pytest tests/test_webhook_dispatcher.py tests/test_webhook_dispatcher_worker.py tests/test_connector_runtime.py -q` - `24 passed`
- `python -m ruff check app tests alembic` - passed
- `python -m pytest -q` - `311 passed`
- `npm test -- executions.test.js DispatchQueuePanel.test.jsx ConnectorWorkspacePanel.test.jsx` - `10 passed`
- `npm test` - `33 passed`
- `npm run build` - passed
- `npm audit --audit-level=high` - `found 0 vulnerabilities`

## Runtime Switches

The dispatcher worker is disabled by default.

Enable it with:

```env
WEBHOOK_DISPATCHER_ENABLED=true
WEBHOOK_DISPATCHER_INTERVAL_SECONDS=5
WEBHOOK_DISPATCHER_BATCH_LIMIT=10
```

## Known Limitations

- No external queue/broker yet.
- No per-tenant dispatcher rate limit yet.
- Retry policy is static: `max_attempts=3`, `backoff_seconds=60`.
- Queue UI reuses the existing executions endpoint and filters webhook executions client-side.
- Queue UI is observability-only; manual replay/dead-letter recovery controls are not part of M11.

## Recommended Next Step

Start M12 as "Operator-grade dispatch controls":

- manual retry for dead-lettered executions;
- pause/resume dispatch per workflow;
- per-trigger rate limits;
- execution search/filter controls in the connector workspace;
- signed webhook auth for production-grade external integrations.
