# M10 TDD Start Checklist

Status: closure passed

## Red Tests To Add First

Frontend API:

- [x] `listConnectors` still calls `/api/v1/connectors`.
- [x] `listConnectorCredentials` supports optional connector filter.
- [x] `createConnectorCredential` posts raw config but returns redacted fixture.
- [x] `deleteConnectorCredential` calls the correct route.
- [x] `createWorkflowTrigger` calls workflow trigger route.
- [x] `listWorkflowTriggers` calls workflow trigger route.

Credential Manager:

- [x] renders credential list with redacted previews.
- [x] owner/editor can open create form.
- [x] viewer does not see create/delete controls.
- [x] successful create clears secret field.
- [x] delete refreshes list.

Connector Config Panel:

- [x] emits M9-compatible connector node data.
- [x] blocks missing URL.
- [x] blocks unsupported method.
- [x] blocks invalid headers JSON.
- [x] blocks invalid query JSON.
- [x] accepts body JSON values.
- [x] updates selected `credential_id`.

Webhook Trigger Panel:

- [x] creates webhook trigger.
- [x] lists existing triggers.
- [x] renders copyable webhook URL.
- [x] shows success feedback after copy.
- [x] viewer can list but not create trigger.

Execution Logs / Doctor:

- [x] connector logs show connector/action/status/error metadata.
- [x] sanitized error is visible.
- [x] raw secret-like values are not rendered.
- [x] `missing_connector_credential` diagnosis shows a recovery action.

## Green Phase Boundaries

Implement only the UI required to satisfy M10 spec:

- no new connector runtimes;
- no OAuth;
- no webhook signing;
- no durable queues;
- no retry execution;
- no AI workflow generation.

## Required Verification

Backend:

```bash
cd backend
python -m ruff check app tests alembic
python -m pytest tests/test_connector_runtime.py -q
python -m pytest -q
```

Frontend:

```bash
cd frontend
npm test
npm run build
npm audit --audit-level=high
```

Smoke:

- [x] create workflow in UI;
- [x] open connector workspace in Builder;
- [x] create credential and verify raw secret is not rendered;
- [x] create webhook trigger;
- [x] copy webhook URL and verify feedback;
- [x] run missing credential diagnosis;
- [x] open credentials from Workflow Doctor recovery action.
- [x] invoke webhook and inspect pending execution/log-empty state.
