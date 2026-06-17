# M9 Acceptance Gate: Connector Runtime and Trigger System

Date: 2026-05-15
Status: passed

## Scope Checked

M9 was accepted against the production-like local dev stack, not only against unit/integration tests.

Checked capabilities:

- backend health and database readiness;
- frontend dev server availability;
- owner registration and tenant creation;
- connector catalog availability;
- HTTP connector credential creation with redacted response;
- webhook trigger creation with public URL;
- public webhook ingestion creating a pending execution;
- cancellation of a pending webhook execution;
- connector node runtime failure on private-network URL;
- connector execution log metadata and sanitized error;
- Workflow Doctor diagnosis for missing connector credential.

## Local Environment

The default local ports `5432`, `5433`, and `8000` were already allocated on the machine during the smoke test.

The acceptance smoke used:

- frontend: `http://127.0.0.1:3000`
- backend: `http://127.0.0.1:8001`
- Postgres host port: `55432`

Backend checks:

- `GET /health` returned `200 {"status":"ok"}`
- `GET /ready` returned `200 {"status":"ready","database":"connected"}`

## Smoke Result

The final smoke run returned:

```json
{
  "connector": "http",
  "credentialRedacted": true,
  "webhookExecutionStatus": "pending",
  "webhookExecutionAfterCancel": "cancelled",
  "privateExecutionStatus": "failed",
  "privateLogNodeType": "connector",
  "doctorDetector": "missing_connector_credential"
}
```

## Acceptance Criteria Status

- `GET /api/v1/connectors` returns the built-in HTTP connector: passed.
- Owners/editors can create HTTP connector credentials: passed.
- Credential responses do not expose raw secrets: passed.
- Viewers cannot create credentials: covered by automated tests.
- Cross-tenant credentials are hidden: covered by automated tests.
- Workflows can have webhook triggers: passed.
- Posting to webhook endpoint creates a pending execution: passed.
- Connector nodes write sanitized connector logs: passed.
- Private-network HTTP targets are blocked: passed.
- Missing connector credential is diagnosed by Workflow Doctor: passed.
- Frontend API helper tests pass: passed.
- Backend integration tests pass: passed.
- Frontend dependency audit at high severity is clean: passed.

## Product Observation

Webhook ingestion creates a `pending` execution, and pending executions count against the tenant's active execution limit. On the free plan, a second manual execution is blocked until the webhook-created pending execution is completed or cancelled.

This is acceptable for M9 because durable trigger queues and trigger execution workers are out of scope. M10 should make this visible in the UI, and a later runtime milestone should add queue semantics.

## Known Limitations Accepted For M9

- No UI yet for connector node creation, credential management, or trigger management.
- Webhook trigger auth is opaque URL only.
- Webhook ingestion creates pending executions but does not auto-run them.
- HTTP connector has one action: `request`.
- No retry policy execution yet, only retryability metadata.
- Connector input is static JSON; no field mapping or templating yet.
- No connector marketplace or OAuth.
