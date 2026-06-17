# M11 Progress: Durable Webhook Dispatch Pipeline

Date: 2026-05-16
Status: slice 4 green

## Completed

- Created M11 idea document.
- Created M11 dispatcher spec.
- Created M11 build config.
- Created M11 TDD start checklist.
- Added failing dispatcher tests first.
- Added `webhook_dispatcher_service`.
- Dispatcher now scans pending executions, filters webhook-triggered runs, dispatches through the existing executor, skips non-webhook pending executions, and respects a batch limit.
- Added failing worker-loop tests first.
- Added config-gated `WebhookDispatcherWorker`.
- Added `WEBHOOK_DISPATCHER_ENABLED`, `WEBHOOK_DISPATCHER_INTERVAL_SECONDS`, and `WEBHOOK_DISPATCHER_BATCH_LIMIT` settings.
- Wired worker installation into FastAPI app bootstrap while keeping it disabled by default.
- Added retry/backoff/dead-letter semantics in `webhook_dispatcher_service`.
- Retryable failed webhook attempts now schedule a new pending execution with lineage metadata.
- Future retry executions are deferred until `dispatch.next_attempt_at`.
- Exhausted retryable attempts are marked `dispatch.dead_lettered = true` without creating another execution.
- Added `listWorkflowDispatchExecutions` on top of the existing execution API.
- Added connector workspace dispatch queue observability.
- Dispatch queue UI shows pending, deferred retry, retry pending, dead-letter, dispatching, completed, and failed states.
- Dispatch queue UI renders only safe execution metadata, not webhook payloads or headers.

## Current Slice

Slice 1 target:

- backend dispatcher service: done;
- backend integration tests: done;
- no external queue or worker loop yet: preserved.

Slice 2 target:

- add config-gated process worker: done;
- keep worker disabled by default: done;
- install worker through FastAPI lifecycle only when enabled: done;
- preserve no external queue/no retry/no frontend boundaries: done.

Slice 3 target:

- retry/backoff policy: done;
- dead-letter metadata: done;
- no new database columns: preserved;
- no frontend changes: preserved.

Slice 4 target:

- queue observability in the connector workspace: done;
- existing executions endpoint reused: done;
- no new backend route: preserved;
- no payload/header rendering in UI: preserved.

## Passing Checks

- `python -m pytest tests/test_webhook_dispatcher_worker.py -q` — `6 passed`.
- `python -m pytest tests/test_webhook_dispatcher.py -q` — `7 passed`.
- `python -m pytest tests/test_webhook_dispatcher.py tests/test_webhook_dispatcher_worker.py tests/test_connector_runtime.py -q` — `24 passed`.
- `python -m pytest tests/test_connector_runtime.py -q` — `11 passed`.
- `python -m ruff check app tests alembic` — passed.
- `python -m pytest -q` — `311 passed`.
- `npm test -- executions.test.js DispatchQueuePanel.test.jsx ConnectorWorkspacePanel.test.jsx` — `10 passed`.
- `npm test` — `33 passed`.
- `npm run build` — passed.
- `npm audit --audit-level=high` — `found 0 vulnerabilities`.

## Pending

- Start M12 planning.
