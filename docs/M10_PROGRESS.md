# M10 Progress: Connector UX and Builder Integration

Date: 2026-05-15
Status: closure passed

## Slice 1 Completed

- Added M10 spec-first artifacts:
  - `docs/M10_CONNECTOR_UX_IDEA.md`
  - `docs/M10_CONNECTOR_UX_SPEC.md`
  - `docs/build-configs/M10_CONNECTOR_UX.yaml`
  - `docs/M10_TDD_START_CHECKLIST.md`
- Added connector node helpers:
  - build M9-compatible `http.request` node data;
  - parse JSON fields;
  - validate URL, method, object JSON fields, body JSON, and timeout.
- Added UI components:
  - `CredentialManager`
  - `ConnectorConfigPanel`
  - `WebhookTriggerPanel`
  - `ConnectorNode`
- Added builder support:
  - HTTP Request node in node palette;
  - connector node type on React Flow canvas;
  - connector nodes persist with `type: connector`;
  - connector nodes do not require agent configs;
  - selected connector node opens connector config panel;
  - existing connector credentials are loaded into builder for selection.
- Added execution support:
  - read-only execution canvas can render connector nodes;
  - LogViewer displays connector/action metadata and sanitized errors.

## Tests Added

- `frontend/src/utils/connectorNode.test.js`
- `frontend/src/components/connectors/CredentialManager.test.jsx`
- `frontend/src/components/connectors/ConnectorConfigPanel.test.jsx`
- `frontend/src/components/connectors/WebhookTriggerPanel.test.jsx`
- `frontend/src/components/execution/LogViewer.test.jsx`
- extended `frontend/src/utils/graphValidation.test.js`

## Passing Checks

- targeted M10 tests: `11 passed`
- full frontend tests: `26 passed`
- frontend production build: passed

## Slice 2 Completed

- Added `ConnectorWorkspacePanel` and wired it into Builder as a real right-side workspace.
- Added Toolbar `Connectors` action for opening credential and webhook management from the canvas.
- Wired credential create/delete to refresh the workspace list after successful mutations.
- Wired webhook trigger creation and copy-to-clipboard success feedback.
- Added Workflow Doctor recovery action for `missing_connector_credential`.
- Connected ExecutionPage Doctor recovery to Builder through router state so the connector workspace opens directly.
- Stabilized connector workspace open/close callbacks in `useBuilder`.

## Slice 2 Tests Added

- `frontend/src/components/connectors/ConnectorWorkspacePanel.test.jsx`
- `frontend/src/components/builder/Toolbar.test.jsx`
- `frontend/src/components/execution/WorkflowDoctorPanel.test.jsx`

## Slice 2 Passing Checks

- targeted Slice 2 frontend tests: `4 passed`
- full frontend tests: `30 passed`
- frontend production build: passed
- frontend audit high severity: `0 vulnerabilities`
- backend connector runtime regression: `11 passed`
- full backend tests: `298 passed`
- backend ruff: passed

## Slice 3 Browser Smoke

- Started local Postgres, backend, and frontend.
- Registered a user through the UI.
- Created a workflow through the UI.
- Opened Builder connector workspace through the Toolbar.
- Created a credential and verified the raw secret was not rendered.
- Created a webhook trigger and verified copy feedback.
- Updated the workflow to contain a connector with a missing credential, started execution, and ran Doctor diagnosis.
- Verified `missing_connector_credential` recovery action opens Builder with connector workspace already visible.
- Fixed clipboard failure handling in `useBuilder` after browser smoke exposed a no-feedback path.
- Invoked a generated webhook URL and verified it creates a pending execution.
- Opened the webhook-created execution in the UI and verified the pending/no-log state.
- Verified webhook secret-like request header is redacted before persistence.

Smoke artifact:

- screenshot: `C:\Users\petro\AppData\Local\Temp\m10-smoke-1778877423328.png`

## Remaining M10 Work

- Optionally add a persistent Playwright smoke script instead of the one-off bundled-runtime smoke.
