# Technical Specification: M10 Connector UX and Builder Integration

## Module Summary

M10 makes the M9 connector runtime usable from the product UI. It adds the first end-to-end connector authoring workflow: credentials, connector nodes, HTTP request configuration, webhook trigger management, connector-aware execution logs, and Workflow Doctor recovery entry points.

M10 should not add new backend connector capabilities unless a small endpoint adjustment is required for UI ergonomics. The default implementation should consume the M9 APIs.

## 1. User Stories

- As an editor, I want to add an HTTP Request connector node in the builder so I can call an external API without editing workflow JSON.
- As an editor, I want to configure method, URL, headers, query, and body for an HTTP node in a structured panel.
- As an editor, I want to select an existing credential for a connector node so secrets are not duplicated across workflows.
- As an editor, I want to create a credential from the connector setup path so I do not have to leave the workflow.
- As an editor, I want to create and copy a webhook trigger URL for a workflow.
- As a viewer, I want to inspect connector logs without seeing secrets.
- As an operator, I want Workflow Doctor to guide me from a missing credential failure back to the connector node or credential manager.

## 2. Existing Backend Contracts

M10 uses these M9 APIs:

- `GET /api/v1/connectors`
- `GET /api/v1/connectors/{connector_key}`
- `POST /api/v1/connector-credentials`
- `GET /api/v1/connector-credentials?connector_key=http`
- `DELETE /api/v1/connector-credentials/{credential_id}`
- `POST /api/v1/workflows/{workflow_id}/triggers`
- `GET /api/v1/workflows/{workflow_id}/triggers`
- `POST /api/v1/webhooks/{public_trigger_id}`
- `GET /api/v1/executions/{execution_id}/logs`
- `POST /api/v1/executions/{execution_id}/diagnose`

No raw credential config may be exposed to the frontend after creation.

## 3. Workflow Definition Shape

Builder must persist connector nodes in the M9-compatible format:

```json
{
  "id": "http-1",
  "type": "connector",
  "position": { "x": 320, "y": 160 },
  "data": {
    "label": "HTTP Request",
    "connector_key": "http",
    "action_key": "request",
    "credential_id": "uuid-or-null",
    "input": {
      "url": "https://example.com/api",
      "method": "GET",
      "headers": {
        "Accept": "application/json"
      },
      "query": {},
      "body": null,
      "timeout_seconds": 20
    }
  }
}
```

Rules:

- agent nodes remain backward compatible;
- connector nodes use `type = "connector"`;
- `connector_key = "http"` and `action_key = "request"` for M10;
- `credential_id` may be `null`;
- `headers`, `query`, and `body` are edited as JSON objects in M10;
- invalid JSON must be blocked before saving the workflow definition.

## 4. Frontend Surfaces

### 4.1 Builder Connector Palette

Add a connector option to the existing workflow builder add-node controls.

Required behavior:

- users can add an `HTTP Request` node;
- node appears visually distinct from agent nodes;
- node has stable dimensions and does not shift layout when selected;
- node displays connector name and action;
- node indicates whether a credential is selected.

### 4.2 Connector Config Panel

When a connector node is selected, show a config panel with:

- label input;
- method select: `GET`, `POST`, `PUT`, `PATCH`, `DELETE`;
- URL input;
- credential mode: `No auth` or `Credential`;
- credential picker filtered by `connector_key=http`;
- create credential action;
- headers JSON editor;
- query JSON editor;
- body JSON editor;
- timeout seconds numeric input.

Validation:

- URL is required;
- method must be one of the allowed methods;
- headers and query must be JSON objects;
- body may be object, array, string, number, boolean, or null;
- timeout must be between `1` and `120`;
- validation errors are shown near the relevant control;
- invalid config cannot be saved into workflow definition.

### 4.3 Credential Manager

M10 may implement this as a dedicated page, drawer, or modal. It must support:

- list credentials;
- filter by connector;
- create HTTP API key header credential;
- show redacted preview;
- delete credential;
- refresh list after create/delete.

Security:

- raw secret is accepted only in the create form;
- after successful create, the raw secret is cleared from component state;
- list view never shows raw secrets;
- delete requires an explicit click, not hover or accidental selection.

### 4.4 Webhook Trigger Panel

On the workflow detail or builder screen, editors can:

- create a webhook trigger;
- list existing triggers;
- copy webhook URL;
- see trigger active status;
- see a short hint that webhook ingestion creates a pending execution in M9.

Viewers can:

- list triggers;
- copy webhook URLs if they can view the workflow.

### 4.5 Execution Logs

Execution logs must render connector metadata:

- `node_type`;
- `connector_key`;
- `action_key`;
- `duration_ms`;
- `retryable`;
- `sanitized_error`;
- HTTP `status_code` when present.

The UI must not render raw request/response objects in a way that exposes secret-like values.

### 4.6 Workflow Doctor Recovery

When Doctor returns `missing_connector_credential`:

- show the diagnosis in the existing Doctor panel;
- provide a visible action to open the relevant connector node or credential manager;
- do not auto-create credentials;
- do not attempt to patch secrets.

## 5. Component/API Design

Suggested frontend modules:

- `frontend/src/api/connectors.js`
- `frontend/src/hooks/useConnectors.js`
- `frontend/src/components/connectors/CredentialManager.jsx`
- `frontend/src/components/connectors/ConnectorConfigPanel.jsx`
- `frontend/src/components/connectors/WebhookTriggerPanel.jsx`
- `frontend/src/components/builder/ConnectorNode.jsx`
- extend `frontend/src/pages/BuilderPage.jsx`
- extend `frontend/src/pages/ExecutionPage.jsx`

Use existing styling patterns and keep operational UI dense and scannable. This is a workflow tool, not a marketing page.

## 6. Error States

Required UI states:

- connector catalog loading;
- connector catalog error;
- credential list loading;
- credential create validation error;
- credential create API error;
- trigger create API error;
- invalid JSON in headers/query/body;
- missing URL;
- missing credential selected but credential list empty;
- execution log has connector error;
- Doctor diagnosis exists but no matching node is present in current workflow view.

## 7. Accessibility And UX Requirements

- Buttons that perform actions should have clear labels and icons where existing app style supports it.
- Copy webhook URL action must have success feedback.
- Inputs must have labels.
- Error text must be close to the invalid control.
- Keyboard navigation through forms should be natural.
- Long webhook URLs and JSON values must wrap or truncate without breaking layout.
- No in-app instructional wall of text; use concise labels and inline states.

## 8. Acceptance Criteria

M10 is complete when:

- An editor can add an HTTP Request connector node in the builder.
- The saved workflow definition matches the M9 connector node contract.
- An editor can create an HTTP API key header credential from UI.
- Raw credential secrets are not shown after create.
- An editor can select a credential for an HTTP Request node.
- Invalid JSON in connector config is blocked before save.
- An editor can create and copy a webhook trigger URL from UI.
- Execution logs render connector metadata and sanitized errors.
- Workflow Doctor missing credential diagnosis offers a UI path to fix setup.
- Existing agent-only builder workflows still work.
- Backend tests remain green.
- Frontend tests and build pass.
- `npm audit --audit-level=high` remains clean.

## 9. Test Plan

### Frontend Unit/API Tests

Extend `frontend/src/api/connectors.test.js`:

- create/list/delete credentials;
- create/list workflow triggers;
- get connector manifest;
- URL encoding for credential filters.

Add component tests where the project test stack supports them:

- `CredentialManager` clears secret after create;
- `CredentialManager` renders redacted previews;
- `ConnectorConfigPanel` blocks invalid JSON;
- `ConnectorConfigPanel` emits M9-compatible node data;
- `WebhookTriggerPanel` creates and displays trigger URL;
- execution log view renders connector metadata.

### Backend Regression Tests

Keep `backend/tests/test_connector_runtime.py` green. Add backend tests only if M10 needs a small API adjustment.

### Smoke Test

Manual or scripted:

1. Register owner.
2. Create workflow in UI.
3. Add HTTP Request node.
4. Create credential.
5. Select credential on node.
6. Create webhook trigger.
7. Copy webhook URL and invoke it.
8. Verify pending execution appears.
9. Run private-network URL case.
10. Verify connector log and Doctor diagnosis.

## 10. Implementation Slices

### Slice 1: Frontend API And Credential Manager

- harden connector API helpers;
- add credential manager UI;
- add tests for create/list/delete and secret clearing.

### Slice 2: Builder Connector Node

- add connector node type;
- add add-node action;
- add config panel;
- persist M9-compatible workflow definition;
- validate URL/method/JSON fields.

### Slice 3: Trigger Panel

- add trigger list/create/copy UI;
- surface pending-execution note in a compact status treatment;
- test trigger create/list behavior.

### Slice 4: Execution And Doctor UX

- render connector log metadata;
- improve connector error display;
- wire Doctor missing credential action to credential manager or builder node focus.

## 11. Out Of Scope

- New backend connector types.
- OAuth.
- Webhook signing.
- Durable queues.
- Retry execution.
- Field mapping UI.
- AI-generated workflow assembly.
- Marketplace.

## 12. Security Requirements

- Do not store raw credential secret in persistent frontend state.
- Clear credential secret input after successful create.
- Do not log raw credential payloads in console.
- Do not render `encrypted_config` or `config`.
- Do not display unredacted request/response secret-like fields.
- Do not add public webhook auth claims beyond current M9 behavior.
- Preserve role restrictions: viewers cannot create/delete credentials or triggers.

## 13. Open Questions

- Should Credentials live as a global page or builder drawer first?
- Should webhook trigger panel live in Builder or Workflow Detail?
- Should connector config use JSON textareas in M10 or a key/value editor immediately?

Recommended decisions:

- Start with a builder drawer/modal for credentials to keep the workflow setup loop tight.
- Put webhook trigger panel in Builder first, then reuse it elsewhere.
- Use JSON textareas for M10 and plan key/value editors for the next UX refinement.
