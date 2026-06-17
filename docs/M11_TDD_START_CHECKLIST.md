# M11 TDD Start Checklist

Status: slice 4 green

## Red Tests To Add First

Dispatcher service:

- [x] detects webhook-triggered executions from execution input data.
- [x] dispatches pending webhook execution to a terminal state through existing executor.
- [x] records connector execution log when dispatched workflow hits connector runtime.
- [x] skips non-webhook pending executions.
- [x] respects `limit=1` for eligible webhook executions.

Regression:

- [x] webhook ingestion still returns pending execution.
- [x] connector runtime tests remain green.

Worker loop:

- [x] worker settings default to disabled.
- [x] worker settings can be explicitly enabled/configured.
- [x] worker `run_once()` dispatches pending webhook execution through a session factory.
- [x] worker loop starts and stops cleanly.
- [x] FastAPI lifecycle installer leaves worker absent when disabled.
- [x] FastAPI lifecycle installer registers worker when enabled.

Retry policy:

- [x] retryable failed webhook attempt schedules a new pending retry execution.
- [x] retry execution stores attempt number and lineage metadata.
- [x] dispatcher defers retry execution until `next_attempt_at`.
- [x] exhausted retryable attempt is marked dead-lettered.
- [x] dead-lettered attempt does not create another execution.

Observability UI:

- [x] execution API helper lists workflow dispatch executions via existing execution endpoint.
- [x] dispatch queue panel renders pending webhook executions.
- [x] dispatch queue panel renders deferred retry and dead-letter states.
- [x] dispatch queue panel displays attempt and next attempt metadata.
- [x] dispatch queue panel does not render webhook payloads or headers.
- [x] connector workspace includes dispatch queue panel.

## Green Phase Boundaries

Slice 1 implemented only the first durable dispatch service.

Slice 2 added only a config-gated worker loop.

Slice 3 may add only retry/backoff/dead-letter semantics:

Slice 4 may add only queue observability:

- no external queue;
- no API endpoint;
- no new database columns;
- no new backend route.

## Required Verification

```bash
cd backend
python -m pytest tests/test_webhook_dispatcher.py -q
python -m pytest tests/test_webhook_dispatcher_worker.py -q
python -m pytest tests/test_connector_runtime.py -q
python -m ruff check app tests alembic
python -m pytest -q
cd ../frontend
npm test
npm run build
npm audit --audit-level=high
```
