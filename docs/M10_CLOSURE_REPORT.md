# M10 Closure Report: Connector UX and Builder Integration

Date: 2026-05-15
Status: closed

## Scope Closed

- Connector workspace is reachable from Builder.
- Credentials can be created, listed, deleted, and displayed with redacted previews.
- HTTP Request connector nodes can be authored and persisted as M9-compatible `connector` nodes.
- Webhook triggers can be created, listed, copied, and invoked.
- Execution UI renders connector-aware logs and empty pending webhook executions.
- Workflow Doctor shows a `missing_connector_credential` recovery action and opens Builder with connector workspace already visible.

## Changed Product Areas

- Frontend connector API client.
- Builder sidebar, toolbar, canvas, node rendering, and builder state hook.
- Credential, connector config, and webhook trigger UI components.
- Execution page, Doctor panel, read-only canvas, and log rendering.
- M10 spec, checklist, build config, progress, and closure docs.

## Verification

Backend:

- `python -m ruff check app tests alembic` — passed.
- `python -m pytest tests/test_connector_runtime.py -q` — `11 passed`.
- `python -m pytest -q` — `298 passed`.

Frontend:

- targeted Slice 2 tests — `4 passed`.
- `npm test` — `30 passed`.
- `npm run build` — passed.
- `npm audit --audit-level=high` — `0 vulnerabilities`.

Browser smoke:

- UI registration passed.
- UI workflow creation passed.
- Builder connector workspace opened from Toolbar.
- Credential create passed and raw secret was not rendered.
- Webhook trigger create and copy feedback passed.
- Missing credential execution failed as expected.
- Doctor diagnosis produced `missing_connector_credential`.
- Doctor `Open credentials` recovery opened Builder with connector workspace visible.
- Webhook invocation created a pending execution.
- Webhook-created execution opened in UI with pending/no-log state.
- Secret-like webhook request header was redacted before persistence.

Smoke artifact:

- `C:\Users\petro\AppData\Local\Temp\m10-smoke-1778877423328.png`

## Security Notes

- Raw credential values are not rendered after credential creation.
- Webhook request headers are redacted before being stored in execution input.
- Clipboard copy now handles browser permission failures with an explicit error toast instead of silently failing.
- Viewer restrictions remain enforced in UI tests for credential and trigger creation controls.

## Known Limitations

- The browser smoke was run as a one-off bundled Playwright script; it is not yet committed as a reusable `npm` script.
- M10 intentionally does not add OAuth, webhook signing, durable queues, or new connector runtimes.
- Webhook ingestion currently creates a pending execution record; a separate dispatcher/worker would be needed to auto-run webhook-triggered executions.
