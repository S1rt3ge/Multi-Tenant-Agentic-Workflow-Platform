# M11 Spec: Durable Webhook Dispatch Pipeline

Date: 2026-05-16
Status: slice 4 green

## Goals

1. Preserve M9/M10 webhook ingestion behavior: POST `/api/v1/webhooks/{public_id}` creates a `pending` execution.
2. Add an internal dispatcher service that can run pending webhook executions.
3. Ensure dispatcher behavior is deterministic and covered by backend integration tests.
4. Keep the first slice deployable without introducing a new external queue dependency.
5. Expose webhook dispatch state in the product UI without leaking webhook payloads or headers.

## Dispatcher Contract

Module:

- `backend/app/services/webhook_dispatcher_service.py`

Public functions:

- `is_webhook_trigger_execution(execution) -> bool`
- `dispatch_pending_webhook_executions(db, limit=10) -> WebhookDispatchReport`

Worker module:

- `backend/app/services/webhook_dispatcher_worker.py`

Public worker API:

- `WebhookDispatcherWorker(session_factory, interval_seconds, batch_limit)`
- `WebhookDispatcherWorker.run_once()`
- `WebhookDispatcherWorker.start()`
- `WebhookDispatcherWorker.stop()`
- `install_webhook_dispatcher_worker(app, settings)`

Report fields:

- `scanned`: number of pending executions inspected.
- `dispatched`: number of webhook executions handed to the executor.
- `skipped`: number of inspected pending executions that were not webhook-triggered.
- `deferred`: number of webhook retry executions skipped until their next attempt time.
- `retries_scheduled`: number of retry executions created.
- `dead_lettered`: number of executions marked as terminally exhausted.
- `execution_ids`: dispatched execution IDs as strings.

Retry policy:

- `WebhookRetryPolicy(max_attempts=3, backoff_seconds=60)`
- retry metadata lives under `execution.input_data.dispatch`.
- failed retryable attempts create a new `pending` execution rather than reusing logs on the failed execution.
- exhausted retryable attempts keep status `failed` and mark `dispatch.dead_lettered = true`.

## Selection Rules

The dispatcher selects executions where:

- `status == "pending"`;
- `input_data.trigger.type == "webhook"`;
- `input_data.dispatch.next_attempt_at` is absent or due;
- execution belongs to an existing workflow and tenant, as already enforced by `run_execution`.

The first slice may scan pending executions and filter JSON in Python to stay compatible with the SQLite test database.

## Execution Rules

For each selected webhook execution:

- call `run_execution(execution.id, execution.workflow_id, execution.tenant_id, execution.input_data, db)`;
- rely on the executor's existing pending-to-running guard to avoid double-running executions;
- allow the executor to produce `completed`, `failed`, or `cancelled` states.
- if the terminal state is retryable failed, schedule a new pending retry execution when attempts remain;
- if attempts are exhausted, mark retry metadata as dead-lettered.

## Security Rules

- Do not rehydrate or log raw webhook headers.
- Do not expose dispatcher as an unauthenticated public endpoint.
- Do not bypass tenant ownership stored on the execution row.
- Do not add hardcoded secrets or external credentials.
- Keep the process-level worker disabled by default.
- Gate process-level startup with `WEBHOOK_DISPATCHER_ENABLED`.
- Dispatch observability UI must not render webhook payloads or headers.

## Observability UI Contract

Location:

- Builder connector workspace.

Data source:

- existing `GET /api/v1/executions?workflow_id=...` response.

Displayed fields:

- compact execution ID;
- derived dispatch state;
- attempt number;
- next attempt time when present;
- created time.

Derived states:

- `Pending`
- `Dispatching`
- `Deferred retry`
- `Retry pending`
- `Dead-letter`
- `Completed`
- `Failed`

## Worker Settings

- `WEBHOOK_DISPATCHER_ENABLED`: bool, default `False`.
- `WEBHOOK_DISPATCHER_INTERVAL_SECONDS`: float, default `5.0`.
- `WEBHOOK_DISPATCHER_BATCH_LIMIT`: int, default `10`.

## Acceptance Criteria

- Existing connector runtime tests remain green.
- New dispatcher tests prove pending webhook execution is dispatched to a terminal state.
- Non-webhook pending execution remains pending.
- `limit=1` dispatches only one eligible webhook execution.
- Worker settings default to disabled.
- Worker `run_once()` dispatches through a session factory.
- Worker loop starts and stops cleanly.
- FastAPI lifecycle installer does not create a worker when disabled.
- FastAPI lifecycle installer registers startup/shutdown hooks when enabled.
- Retryable failed webhook attempts schedule a new pending execution.
- Future-dated retry executions are deferred.
- Exhausted retryable attempts are marked dead-lettered without creating a new execution.
- Connector workspace shows recent webhook dispatch executions.
- Dispatch observability UI shows pending/deferred/dead-letter states.
- Dispatch observability UI does not render webhook payload or headers.
- Full backend test suite remains green.

## Future Slices

- M11 Slice 2: optional process-level worker loop gated by config.
- M11 Slice 3: retry/backoff and dead-letter states.
- M11 Slice 4: UI observability for queued/dispatching webhook runs.
