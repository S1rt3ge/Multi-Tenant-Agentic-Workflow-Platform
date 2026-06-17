# Technical Specification: M9 Connector Runtime and Trigger System

## Module Summary

M9 turns GraphPilot from an internal workflow runner into an integration platform. It adds connector manifests, tenant-scoped credentials, webhook/manual triggers, connector action execution, sanitized connector logs, and the first connector-aware Workflow Doctor detector.

The MVP vertical slice must be intentionally narrow:

- one built-in connector runtime: `http.request`;
- one trigger type beyond manual execution: `webhook`;
- tenant-scoped credential storage with redacted responses;
- connector node execution from workflow definitions;
- execution logs that show connector status without leaking secrets;
- Workflow Doctor detects missing connector credentials.

Do not build a connector marketplace, OAuth, schedules, or durable queues in M9. Those belong to later milestones.

## 1. User Stories

- As an editor, I want to add an HTTP connector node to a workflow so the workflow can call an external API.
- As an editor, I want to store a connector credential once and reference it from a connector node without exposing secret values in the UI.
- As an editor, I want to create a webhook trigger for a workflow so external systems can start executions.
- As a viewer, I want to inspect connector execution logs without seeing raw secrets.
- As an owner, I want connector credentials and webhook events to stay tenant-scoped.
- As a platform developer, I want connector behavior to be manifest-driven so new connectors do not require changes to core workflow CRUD.
- As an operator, I want Workflow Doctor to identify when a connector node failed because its credential is missing or unavailable.

## 2. Data Model

### 2.1 `connectors`

Global connector catalog. These rows are not tenant-owned.

```sql
CREATE TABLE connectors (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    key TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    version TEXT NOT NULL DEFAULT '1.0.0',
    manifest JSONB NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_connectors_active ON connectors(is_active);
```

MVP seed connector:

```json
{
  "key": "http",
  "name": "HTTP",
  "version": "1.0.0",
  "auth_types": ["none", "api_key_header"],
  "actions": [
    {
      "key": "request",
      "name": "Request",
      "input_schema": {
        "type": "object",
        "required": ["url", "method"],
        "properties": {
          "url": { "type": "string", "format": "uri" },
          "method": { "type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"] },
          "headers": { "type": "object" },
          "query": { "type": "object" },
          "body": {}
        }
      },
      "output_schema": {
        "type": "object",
        "properties": {
          "status_code": { "type": "integer" },
          "headers": { "type": "object" },
          "body": {}
        }
      },
      "retry": {
        "max_attempts": 1,
        "retryable_statuses": [408, 429, 500, 502, 503, 504]
      }
    }
  ]
}
```

### 2.2 `connector_credentials`

Tenant-owned credential references.

```sql
CREATE TABLE connector_credentials (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    connector_key TEXT NOT NULL,
    name TEXT NOT NULL,
    auth_type TEXT NOT NULL,
    encrypted_config JSONB NOT NULL,
    config_preview JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_connector_credentials_tenant
    ON connector_credentials(tenant_id);

CREATE INDEX idx_connector_credentials_connector
    ON connector_credentials(tenant_id, connector_key);

CREATE UNIQUE INDEX uq_connector_credentials_tenant_name_active
    ON connector_credentials(tenant_id, name)
    WHERE is_active = true;
```

MVP encryption rule:

- If the project already has an encryption helper, use it.
- If not, create a single server-side credential codec abstraction and back it with Fernet or another authenticated encryption primitive.
- Never store raw credential config in `config_preview`.
- `config_preview` may include masked labels such as:

```json
{
  "header_name": "Authorization",
  "header_value": "********oken"
}
```

### 2.3 `workflow_triggers`

Tenant-owned workflow trigger definitions.

```sql
CREATE TABLE workflow_triggers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    trigger_type TEXT NOT NULL,
    public_id TEXT NOT NULL UNIQUE,
    config JSONB NOT NULL DEFAULT '{}',
    is_active BOOLEAN NOT NULL DEFAULT true,
    created_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_workflow_triggers_workflow
    ON workflow_triggers(tenant_id, workflow_id);

CREATE INDEX idx_workflow_triggers_type
    ON workflow_triggers(tenant_id, trigger_type);
```

Allowed MVP `trigger_type`:

- `webhook`
- `manual`

The existing `POST /workflows/{wf_id}/execute` remains the manual trigger path. A `manual` trigger row is optional in MVP.

### 2.4 `webhook_events`

Audit trail for webhook ingestion.

```sql
CREATE TABLE webhook_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    trigger_id UUID NOT NULL REFERENCES workflow_triggers(id) ON DELETE CASCADE,
    execution_id UUID REFERENCES executions(id) ON DELETE SET NULL,
    payload JSONB,
    headers_sanitized JSONB NOT NULL DEFAULT '{}',
    status TEXT NOT NULL DEFAULT 'received',
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_webhook_events_trigger
    ON webhook_events(tenant_id, trigger_id, created_at);

CREATE INDEX idx_webhook_events_execution
    ON webhook_events(tenant_id, execution_id);
```

Allowed `status` values:

- `received`
- `execution_created`
- `rejected`
- `failed`

### 2.5 Extend `execution_logs`

Add nullable connector metadata:

```sql
ALTER TABLE execution_logs ADD COLUMN node_id TEXT;
ALTER TABLE execution_logs ADD COLUMN node_type TEXT;
ALTER TABLE execution_logs ADD COLUMN connector_key TEXT;
ALTER TABLE execution_logs ADD COLUMN action_key TEXT;
ALTER TABLE execution_logs ADD COLUMN attempt INTEGER NOT NULL DEFAULT 1;
ALTER TABLE execution_logs ADD COLUMN retryable BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE execution_logs ADD COLUMN sanitized_error TEXT;
```

MVP must remain backward compatible with existing agent logs.

## 3. Workflow Definition Format

MVP adds connector nodes while preserving existing agent nodes.

```json
{
  "nodes": [
    {
      "id": "http-1",
      "type": "connector",
      "position": { "x": 320, "y": 120 },
      "data": {
        "label": "Fetch Lead",
        "connector_key": "http",
        "action_key": "request",
        "credential_id": "uuid-or-null",
        "input": {
          "url": "https://example.com/api/leads",
          "method": "GET",
          "headers": {
            "Accept": "application/json"
          }
        }
      }
    }
  ],
  "edges": []
}
```

Connector node rules:

- `type` defaults to `agent` if missing for old workflows.
- `connector_key` and `action_key` are required for connector nodes.
- `credential_id` is optional only when the connector action allows `auth_type = none`.
- `input` must be a JSON object.
- Runtime must validate connector node config before executing the action.

## 4. API

### 4.1 List connectors

```http
GET /api/v1/connectors
```

Roles:

- `owner`, `editor`, `viewer`

Response `200`:

```json
{
  "items": [
    {
      "key": "http",
      "name": "HTTP",
      "description": "Make HTTP requests",
      "version": "1.0.0",
      "actions": [
        {
          "key": "request",
          "name": "Request"
        }
      ]
    }
  ]
}
```

### 4.2 Get connector

```http
GET /api/v1/connectors/{connector_key}
```

Response `200` includes manifest without secrets.

### 4.3 Create credential

```http
POST /api/v1/connector-credentials
```

Roles:

- `owner`, `editor`

Request:

```json
{
  "connector_key": "http",
  "name": "Example API",
  "auth_type": "api_key_header",
  "config": {
    "header_name": "Authorization",
    "header_value": "Bearer secret-token"
  }
}
```

Response `201`:

```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "connector_key": "http",
  "name": "Example API",
  "auth_type": "api_key_header",
  "config_preview": {
    "header_name": "Authorization",
    "header_value": "********oken"
  },
  "is_active": true,
  "created_at": "2026-05-15T00:00:00Z"
}
```

Response must never include:

- `config`
- `encrypted_config`
- raw secret values

### 4.4 List credentials

```http
GET /api/v1/connector-credentials?connector_key=http
```

Roles:

- `owner`, `editor`, `viewer`

Response returns redacted credential records only.

### 4.5 Delete credential

```http
DELETE /api/v1/connector-credentials/{credential_id}
```

Roles:

- `owner`, `editor`

MVP uses soft delete:

- `is_active = false`

### 4.6 Create workflow trigger

```http
POST /api/v1/workflows/{workflow_id}/triggers
```

Roles:

- `owner`, `editor`

Request:

```json
{
  "trigger_type": "webhook",
  "config": {
    "auth": "none"
  }
}
```

Response `201`:

```json
{
  "id": "uuid",
  "workflow_id": "uuid",
  "trigger_type": "webhook",
  "public_id": "opaque-public-id",
  "webhook_url": "http://localhost:8000/api/v1/webhooks/opaque-public-id",
  "is_active": true
}
```

### 4.7 List workflow triggers

```http
GET /api/v1/workflows/{workflow_id}/triggers
```

Roles:

- `owner`, `editor`, `viewer`

### 4.8 Ingest webhook

```http
POST /api/v1/webhooks/{public_trigger_id}
```

Auth:

- Public endpoint in MVP.
- Uses opaque `public_trigger_id`.
- M14 will add policy and signing.

Behavior:

- Find active webhook trigger.
- Store sanitized webhook event.
- Create pending execution with input:

```json
{
  "trigger": {
    "type": "webhook",
    "trigger_id": "uuid",
    "event_id": "uuid"
  },
  "payload": {},
  "headers": {}
}
```

Response `202`:

```json
{
  "execution_id": "uuid",
  "status": "pending"
}
```

## 5. Services

### 5.1 `connector_manifest_service`

Responsibilities:

- Seed built-in connector manifests.
- List active connectors.
- Fetch connector manifests by key.
- Validate connector/action existence.
- Return public manifest shape.

### 5.2 `connector_credential_service`

Responsibilities:

- Validate credential config against connector auth type.
- Encrypt config before persistence.
- Build redacted `config_preview`.
- Decrypt config only inside runtime.
- Enforce tenant access.

### 5.3 `connector_runtime_service`

Responsibilities:

- Execute connector node actions.
- Validate action input.
- Resolve credential when required.
- Apply credential to request.
- Enforce network safety.
- Return normalized output.
- Return sanitized error details.

### 5.4 `trigger_service`

Responsibilities:

- Create/list workflow triggers.
- Generate opaque public ids.
- Validate workflow ownership.
- Disable triggers when needed.

### 5.5 `webhook_ingestion_service`

Responsibilities:

- Resolve public trigger id.
- Sanitize incoming headers.
- Store webhook event.
- Create execution through execution service.
- Update event status and execution id.

## 6. Runtime Business Logic

### 6.1 Connector Execution

Connector nodes execute as workflow steps.

MVP options:

1. Integrate connector execution into the existing executor loop.
2. Keep agent behavior unchanged and branch by `node.type`.

For connector nodes:

1. Load node data.
2. Validate connector/action.
3. Validate input object.
4. Resolve credential if needed.
5. Execute action.
6. Write `ExecutionLog` with connector metadata.
7. Store connector output in workflow state.

### 6.2 HTTP Request Action

Supported input:

- `url`
- `method`
- `headers`
- `query`
- `body`
- `timeout_seconds`

Defaults:

- `method = GET`
- `timeout_seconds = 20`
- no redirects in MVP unless explicitly allowed later

Output:

```json
{
  "status_code": 200,
  "headers": {},
  "body": {},
  "text_preview": "first 2048 characters if body is text"
}
```

### 6.3 Network Safety

HTTP connector must block:

- `localhost`
- `127.0.0.0/8`
- `0.0.0.0/8`
- `10.0.0.0/8`
- `172.16.0.0/12`
- `192.168.0.0/16`
- `169.254.0.0/16`
- IPv6 loopback and link-local addresses
- non-HTTP schemes

MVP may allow `https://example.com/` in tests and smoke scripts.

### 6.4 Secret Redaction

Redact keys containing:

- `authorization`
- `cookie`
- `password`
- `secret`
- `token`
- `api_key`
- `apikey`
- `access_key`
- `private_key`

Redaction applies to:

- credential previews;
- request headers in logs;
- response headers in logs;
- webhook headers;
- error strings where possible;
- Workflow Doctor root cause and recommendation text.

### 6.5 Workflow Doctor Integration

Add detectors:

- `missing_connector_credential`
- `connector_credential_inactive`
- `connector_network_blocked`
- `connector_http_error`

M9 MVP must implement at least:

- `missing_connector_credential`

Detector behavior:

- If connector node requires credential and `credential_id` is missing or not found, create suggestion with no auto patch.
- Recommendation: create or select a credential for the connector node.
- Severity: `high`
- Patch: `{"operations": []}`

## 7. Screens / Components

### 7.1 Connector Library

MVP can be a simple page or drawer:

- connector name
- description
- actions
- auth types

### 7.2 Credential Manager

Required MVP:

- list credentials;
- create HTTP API key header credential;
- show redacted preview;
- delete credential.

### 7.3 Builder Connector Node

Required MVP:

- add connector node;
- select connector `HTTP`;
- select action `Request`;
- select credential or no auth;
- edit URL/method/headers/body JSON.

If full Builder integration is too large for the first M9 slice, implement API and a minimal config path first, then wire Builder in the second M9 slice.

### 7.4 Execution Logs

LogViewer should display:

- node type;
- connector/action;
- status code;
- sanitized error;
- duration;
- retryable flag.

### 7.5 Workflow Doctor

Doctor panel should show connector-specific diagnosis using the existing M8 panel.

## 8. Edge Cases

- Credential belongs to another tenant.
- Credential is inactive.
- Credential raw secret appears in connector response body.
- Webhook payload is not JSON.
- Webhook headers include secrets.
- Webhook public id does not exist.
- Trigger exists but workflow is inactive.
- Workflow has connector node with missing `connector_key`.
- Workflow has connector node with unsupported `action_key`.
- HTTP URL points to private network.
- HTTP response is huge.
- HTTP response is binary.
- HTTP request times out.
- HTTP request returns 429.
- Connector action fails after execution log is partially written.
- Existing agent-only workflow still runs unchanged.

## 9. Acceptance Criteria

M9 MVP is complete when:

- `GET /api/v1/connectors` returns the built-in HTTP connector.
- Owners/editors can create HTTP connector credentials.
- Credential responses never expose raw secrets.
- Viewers can list redacted credentials but cannot create/delete credentials.
- A workflow can have a webhook trigger.
- Posting to the webhook endpoint creates a pending execution.
- A connector node can execute `http.request` and write a sanitized connector log.
- Missing connector credential failure is diagnosed by Workflow Doctor.
- Cross-tenant credential and trigger access returns `404` or `403` as appropriate.
- Backend and frontend tests pass.
- `npm audit --audit-level=high` remains clean.

## 10. Test Plan

### Backend Tests

Create `backend/tests/test_connector_runtime.py`.

Test cases:

- `test_list_connectors_includes_http_manifest`
- `test_create_credential_redacts_secret`
- `test_viewer_cannot_create_credential`
- `test_cross_tenant_credential_hidden`
- `test_delete_credential_soft_deletes`
- `test_create_webhook_trigger_returns_public_url`
- `test_webhook_creates_pending_execution`
- `test_webhook_unknown_public_id_returns_404`
- `test_http_connector_blocks_private_network`
- `test_http_connector_logs_sanitized_failure`
- `test_workflow_doctor_detects_missing_connector_credential`

### Frontend Tests

Create or extend:

- `frontend/src/api/connectors.test.js`
- `frontend/src/api/executions.test.js`

Test cases:

- list connectors calls `/api/v1/connectors`
- create credential posts config but response fixtures are redacted
- list workflow triggers calls the correct route
- webhook URL formatting is stable

### Smoke Test

Use disposable Postgres or test DB:

1. Run migrations.
2. Register owner.
3. Create workflow with connector node.
4. Create webhook trigger.
5. POST webhook payload.
6. Assert execution is created.
7. Diagnose missing credential if connector has none.

## 11. Implementation Slices

### Slice 1: Backend Foundation

- models;
- migration;
- schemas;
- connector manifest seed;
- credential create/list/delete;
- trigger create/list;
- webhook ingestion;
- tests.

### Slice 2: Runtime Integration

- connector node definition support;
- HTTP action runtime;
- execution log metadata;
- network safety;
- sanitized errors;
- tests.

### Slice 3: Workflow Doctor Integration

- missing credential detector;
- connector-specific diagnosis text;
- tests.

### Slice 4: Frontend MVP

- API helpers;
- credential manager;
- trigger panel;
- minimal connector node config support;
- tests/build.

## 12. Out of Scope for M9

- OAuth flows.
- Schedules.
- Queues and durable retries.
- Connector marketplace.
- User-installed connector packages.
- Complex field mapping UI.
- Typed contracts.
- Approval policies.
- Multi-step connector transactions.

## 13. Security Requirements

- No raw credentials in API responses.
- No raw credentials in execution logs.
- No raw credentials in webhook event headers.
- Tenant filter on every credential, trigger, and webhook event query.
- Public webhook ids must be high-entropy opaque ids.
- HTTP connector must block private networks and non-HTTP schemes.
- Connector errors must be sanitized before returning to users.
- Tests must explicitly assert secret redaction.

## 14. Open Questions

- Should credential encryption use an existing project secret or a new `CREDENTIAL_ENCRYPTION_KEY`?
- Should webhook triggers support simple shared-secret header auth in M9.1 or wait until M14 policy?
- Should connector node support templated input values in M9 or wait for M11 typed mappings?

Recommended decisions:

- Add `CREDENTIAL_ENCRYPTION_KEY` with development fallback only when `APP_ENV=development`.
- Keep webhook auth as opaque URL only for M9.
- Keep connector input static JSON in M9; add mappings in M11.
