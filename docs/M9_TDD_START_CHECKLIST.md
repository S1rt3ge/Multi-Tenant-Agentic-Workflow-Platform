# M9 TDD Start Checklist

Use this checklist before writing M9 implementation code.

## Step 1 - Red Backend Tests

Create `backend/tests/test_connector_runtime.py` with these failing tests first:

1. `test_list_connectors_includes_http_manifest`
2. `test_create_credential_redacts_secret`
3. `test_viewer_cannot_create_credential`
4. `test_cross_tenant_credential_hidden`
5. `test_delete_credential_soft_deletes`
6. `test_create_webhook_trigger_returns_public_url`
7. `test_webhook_creates_pending_execution`
8. `test_webhook_unknown_public_id_returns_404`
9. `test_http_connector_blocks_private_network`
10. `test_http_connector_logs_sanitized_failure`
11. `test_workflow_doctor_detects_missing_connector_credential`

Expected initial result:

```powershell
cd backend
python -m pytest tests/test_connector_runtime.py -q
```

The tests should fail because routes, models, and services do not exist yet.

## Step 2 - Red Frontend Tests

Create `frontend/src/api/connectors.test.js` before frontend implementation.

Minimum failing tests:

1. `listConnectors` calls `/api/v1/connectors`
2. `createConnectorCredential` posts credential config
3. `listConnectorCredentials` calls `/api/v1/connector-credentials`
4. `deleteConnectorCredential` calls the credential delete route
5. `createWorkflowTrigger` calls `/api/v1/workflows/{id}/triggers`
6. `listWorkflowTriggers` calls the same workflow trigger collection route

Expected initial result:

```powershell
cd frontend
npm test
```

The tests should fail because API helpers do not exist yet.

## Step 3 - Green Backend Foundation

Implement only enough backend code to pass the foundation tests:

- connector manifest listing;
- credential create/list/delete with redaction;
- webhook trigger create/list;
- webhook ingestion creates pending execution;
- tenant isolation.

Do not implement connector runtime execution until the foundation tests are green.

## Step 4 - Green Runtime Slice

Implement:

- connector node validation;
- HTTP request action;
- private network blocking;
- sanitized connector logs;
- existing agent workflow compatibility.

## Step 5 - Green Doctor Slice

Implement:

- `missing_connector_credential` detector;
- Doctor response with severity `high`;
- no auto patch for missing credentials.

## Step 6 - Frontend MVP

Implement:

- connector API helpers;
- trigger API helpers;
- minimal credential manager UI;
- minimal trigger panel UI;
- connector-aware execution log display if backend metadata is present.

## Step 7 - Verification

Run:

```powershell
cd backend
python -m ruff check app tests
python -m pytest tests/test_connector_runtime.py -q
python -m pytest tests/test_workflow_doctor.py -q
python -m pytest -q
python -m alembic upgrade head --sql

cd ../frontend
npm test
npm run build
npm audit --audit-level=high
```

## Stop Conditions

Stop and fix before continuing if:

- a credential value appears in any API response;
- a credential value appears in execution logs;
- cross-tenant credential access returns `200`;
- HTTP connector allows localhost/private-network calls;
- existing agent-only execution tests fail;
- frontend build fails;
- `npm audit --audit-level=high` fails.
