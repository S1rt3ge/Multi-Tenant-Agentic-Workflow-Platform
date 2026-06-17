# Technical Specification: M8 Workflow Doctor

## Module Summary

Workflow Doctor diagnoses failed executions, stores repair suggestions, previews safe patches, validates fixes through sandbox replay, and lets users apply approved patches before retrying.

This module extends the existing execution system. It does not replace the executor.

## 1. User Stories

- As an editor, I want to diagnose a failed execution so I can understand the root cause without manually reading every log.
- As an editor, I want to preview a suggested fix before applying it so I can avoid accidental workflow damage.
- As an editor, I want to run a sandbox replay before retrying so I can validate that the workflow configuration is now coherent.
- As a viewer, I want to read diagnosis output so I can understand failures without being able to mutate the workflow.
- As an owner, I want repair history to stay tenant-scoped so one tenant can never see another tenant's failed runs or suggestions.

## 2. Data Model

### 2.1 `workflow_fix_suggestions`

```sql
CREATE TABLE workflow_fix_suggestions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    execution_id UUID NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
    node_id TEXT,
    agent_config_id UUID REFERENCES agent_configs(id),
    tool_id UUID REFERENCES tool_registry(id),
    status TEXT NOT NULL DEFAULT 'proposed',
    severity TEXT NOT NULL DEFAULT 'medium',
    detector_code TEXT NOT NULL,
    title TEXT NOT NULL,
    root_cause TEXT NOT NULL,
    recommendation TEXT NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 0.0,
    patch JSONB NOT NULL DEFAULT '{"operations": []}',
    replay_result JSONB,
    applied_at TIMESTAMPTZ,
    applied_by UUID REFERENCES users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_fix_suggestions_tenant_execution
    ON workflow_fix_suggestions(tenant_id, execution_id);

CREATE INDEX idx_fix_suggestions_tenant_workflow
    ON workflow_fix_suggestions(tenant_id, workflow_id);

CREATE INDEX idx_fix_suggestions_status
    ON workflow_fix_suggestions(tenant_id, status);
```

Allowed `status` values:

- `proposed`
- `replay_passed`
- `replay_failed`
- `applied`
- `dismissed`

Allowed `severity` values:

- `low`
- `medium`
- `high`
- `critical`

### 2.2 `workflow_replay_runs`

```sql
CREATE TABLE workflow_replay_runs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    workflow_id UUID NOT NULL REFERENCES workflows(id) ON DELETE CASCADE,
    execution_id UUID NOT NULL REFERENCES executions(id) ON DELETE CASCADE,
    suggestion_id UUID REFERENCES workflow_fix_suggestions(id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    mode TEXT NOT NULL DEFAULT 'validation_only',
    input_snapshot JSONB,
    result JSONB,
    error_message TEXT,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_replay_runs_tenant_execution
    ON workflow_replay_runs(tenant_id, execution_id);
```

Allowed `status` values:

- `pending`
- `running`
- `passed`
- `failed`

MVP supports only `validation_only` mode.

### 2.3 RLS / Tenant Isolation Equivalent

The current backend does not use database-level RLS. Tenant isolation is enforced through service-layer filters.

Every query in this module must include:

```python
WorkflowFixSuggestion.tenant_id == tenant_id
WorkflowReplayRun.tenant_id == tenant_id
Execution.tenant_id == tenant_id
Workflow.tenant_id == tenant_id
```

Tests must verify that a user from tenant A receives `404` for tenant B suggestions, executions, and replay runs.

## 3. Patch Format

`patch` is JSONB with a strict operation list.

```json
{
  "operations": [
    {
      "op": "replace",
      "target_type": "tool",
      "target_id": "uuid",
      "path": "/config/url",
      "current_value_preview": "https://bad.example.invalid",
      "value": "https://example.com/",
      "secret": false
    }
  ]
}
```

Allowed `op` values in MVP:

- `replace`
- `add`

Allowed `target_type` values in MVP:

- `workflow`
- `agent_config`
- `tool`

Allowed paths in MVP:

- `/definition`
- `/execution_pattern`
- `/system_prompt`
- `/model`
- `/max_tokens`
- `/temperature`
- `/config/url`
- `/config/method`
- `/config/body_template`
- `/config/query_template`
- `/config/allowed_extensions`

Blocked paths:

- password fields;
- connection string replacement;
- raw secret headers;
- user and tenant fields;
- execution history fields;
- cost or token counters.

Secret rule:

- Suggestions may preserve existing masked secrets.
- Suggestions must never generate or display a new raw secret.

## 4. API

### 4.1 Diagnose execution

```http
POST /api/v1/executions/{execution_id}/diagnose
```

Roles:

- `owner`, `editor`, `viewer`

Request:

```json
{
  "force": false
}
```

Response `201`:

```json
{
  "items": [
    {
      "id": "uuid",
      "execution_id": "uuid",
      "workflow_id": "uuid",
      "node_id": "node-1",
      "status": "proposed",
      "severity": "high",
      "detector_code": "api_url_resolution_failed",
      "title": "API tool host cannot be resolved",
      "root_cause": "The tool URL host failed DNS resolution during validation.",
      "recommendation": "Use a resolvable HTTPS endpoint or update the tool URL.",
      "confidence": 0.92,
      "patch": {
        "operations": []
      },
      "created_at": "2026-05-14T12:00:00Z"
    }
  ]
}
```

Errors:

- `401` invalid auth
- `404` execution not found
- `409` execution is not failed or cancelled
- `422` execution has no logs or no diagnosable state

Behavior:

- If suggestions already exist and `force=false`, return existing active suggestions.
- If `force=true`, mark old `proposed` suggestions as `dismissed` and create fresh suggestions.

### 4.2 List suggestions for execution

```http
GET /api/v1/executions/{execution_id}/fix-suggestions
```

Roles:

- `owner`, `editor`, `viewer`

Response `200`:

```json
{
  "items": [],
  "total": 0
}
```

### 4.3 Replay suggestion

```http
POST /api/v1/fix-suggestions/{suggestion_id}/replay
```

Roles:

- `owner`, `editor`

Request:

```json
{
  "mode": "validation_only"
}
```

Response `201`:

```json
{
  "id": "uuid",
  "suggestion_id": "uuid",
  "status": "passed",
  "mode": "validation_only",
  "result": {
    "graph_valid": true,
    "agent_configs_valid": true,
    "tool_configs_valid": true,
    "external_calls_executed": false
  }
}
```

Errors:

- `404` suggestion not found
- `409` suggestion already applied or dismissed
- `422` unsupported replay mode

### 4.4 Apply suggestion

```http
POST /api/v1/fix-suggestions/{suggestion_id}/apply
```

Roles:

- `owner`, `editor`

Request:

```json
{
  "retry": true
}
```

Response `200`:

```json
{
  "suggestion_id": "uuid",
  "status": "applied",
  "retry_execution_id": "uuid"
}
```

Errors:

- `404` suggestion not found
- `409` suggestion already applied
- `422` patch has blocked operation
- `422` replay failed and retry requested

Behavior:

- Patch application is transactional.
- If any operation fails validation, no operation is applied.
- If `retry=true`, create a new execution after applying the patch.

### 4.5 Dismiss suggestion

```http
POST /api/v1/fix-suggestions/{suggestion_id}/dismiss
```

Roles:

- `owner`, `editor`

Response `200`:

```json
{
  "suggestion_id": "uuid",
  "status": "dismissed"
}
```

## 5. Diagnosis Detectors

### 5.1 `missing_provider_key`

Input:

- execution failed with `OPENAI_API_KEY not configured` or `ANTHROPIC_API_KEY not configured`.

Output:

- severity: `high`
- patch: none
- recommendation: configure provider key in environment.

### 5.2 `unsupported_model`

Input:

- agent failure includes `Unsupported model`.

Output:

- severity: `high`
- patch: replace `/model` with supported model from `gpt-4o`, `gpt-4o-mini`, `claude-sonnet`, `claude-opus`.

### 5.3 `missing_agent_config`

Input:

- compilation error contains `Agent configs missing for nodes`.

Output:

- severity: `critical`
- patch: add default agent config for missing node only if node id exists in workflow definition.

### 5.4 `invalid_workflow_graph`

Input:

- validation error contains orphan nodes, unknown edge source, unknown edge target, or no nodes.

Output:

- severity: `critical`
- patch: none in MVP.
- recommendation: open Builder and reconnect graph.

### 5.5 `api_url_resolution_failed`

Input:

- tool validation or execution error contains `Unable to resolve API URL host`.

Output:

- severity: `high`
- patch: replace `/config/url` only when a safe replacement can be inferred from previous successful config or user-provided replay input.
- MVP patch may be empty with manual recommendation.

### 5.6 `restricted_api_network`

Input:

- error contains `restricted network`, `localhost`, or `Only https API URLs are allowed`.

Output:

- severity: `high`
- patch: none by default.
- recommendation: use public HTTPS endpoint or configure a safe gateway.

### 5.7 `database_query_not_read_only`

Input:

- tool result contains `Only read-only database queries are allowed`.

Output:

- severity: `medium`
- patch: none.
- recommendation: replace query with SELECT/SHOW/PRAGMA read-only query.

### 5.8 `budget_exceeded`

Input:

- execution error contains `Monthly token budget exceeded`.

Output:

- severity: `medium`
- patch: reduce agent `max_tokens` only if the failed step has an agent config.

### 5.9 `cyclic_iteration_limit`

Input:

- execution error contains `Max iterations exceeded`.

Output:

- severity: `high`
- patch: add stricter routing instruction to system prompt.

### 5.10 `no_diagnosis_available`

Input:

- no detector matches.

Output:

- severity: `low`
- patch: none.
- recommendation: inspect logs manually.

## 6. Backend Services

### 6.1 `diagnosis_service.py`

Functions:

```python
async def diagnose_execution(db, tenant_id, execution_id, force=False) -> list[WorkflowFixSuggestion]
async def list_suggestions(db, tenant_id, execution_id) -> list[WorkflowFixSuggestion]
```

Responsibilities:

- load execution and logs;
- load workflow, agent configs, and tool configs;
- run detectors in deterministic priority order;
- persist suggestions;
- mask sensitive config previews.

### 6.2 `patch_service.py`

Functions:

```python
async def preview_patch(db, tenant_id, suggestion_id) -> dict
async def apply_suggestion(db, tenant_id, suggestion_id, user_id, retry=False) -> dict
```

Responsibilities:

- validate operation targets;
- block disallowed paths;
- apply patch transactionally;
- update suggestion status;
- optionally create retry execution.

### 6.3 `replay_service.py`

Functions:

```python
async def replay_suggestion(db, tenant_id, suggestion_id, mode="validation_only") -> WorkflowReplayRun
```

Responsibilities:

- clone relevant workflow/config state in memory;
- apply patch in memory;
- validate graph;
- validate agent configs;
- validate tool configs without external calls;
- persist replay result.

## 7. Frontend

### 7.1 Execution page changes

File:

```text
frontend/src/pages/ExecutionPage.jsx
```

Add:

- `Diagnose` button when execution status is `failed` or `cancelled`.
- `WorkflowDoctorPanel` in the right column under logs or as a side panel.

### 7.2 New API client

File:

```text
frontend/src/api/fixSuggestions.js
```

Functions:

```javascript
diagnoseExecution(executionId, force = false)
listFixSuggestions(executionId)
replayFixSuggestion(suggestionId)
applyFixSuggestion(suggestionId, retry = true)
dismissFixSuggestion(suggestionId)
```

### 7.3 New hook

File:

```text
frontend/src/hooks/useWorkflowDoctor.js
```

State:

- `suggestions`
- `isDiagnosing`
- `isReplaying`
- `isApplying`
- `error`
- `selectedSuggestion`

### 7.4 New components

```text
frontend/src/components/doctor/WorkflowDoctorPanel.jsx
frontend/src/components/doctor/FixSuggestionCard.jsx
frontend/src/components/doctor/PatchPreview.jsx
frontend/src/components/doctor/ReplayResult.jsx
```

UI states:

- empty: no diagnosis yet;
- diagnosing;
- suggestions loaded;
- replay passed;
- replay failed;
- apply success;
- apply error.

Viewer behavior:

- viewers can diagnose and read suggestions;
- viewers cannot replay, apply, or dismiss.

## 8. Business Logic

- Diagnosis can run only for executions in terminal states: `failed`, `cancelled`, `completed`.
- For `completed`, diagnosis returns only low-severity optimization suggestions in v2. MVP may return `422`.
- Apply requires `owner` or `editor`.
- Patch cannot modify execution history.
- Patch cannot write secrets.
- Patch cannot cross tenant boundaries.
- Replay must not execute external API, database, file-system, or LLM calls in MVP.
- Retry after apply creates a new execution and keeps the original execution immutable.

## 9. Edge Cases

- Execution not found: return `404`.
- Execution belongs to another tenant: return `404`.
- Suggestion belongs to another tenant: return `404`.
- Suggestion already applied: return `409`.
- Replay failed: apply with retry returns `422`.
- Patch target deleted since diagnosis: return `409`.
- Tool config contains masked placeholders: preserve original raw values in DB, show only masked previews.
- Multiple suggestions exist: user applies one at a time.
- Diagnosis produces duplicate detector output: keep highest-confidence suggestion per detector code.
- Concurrent apply requests: first request wins; second returns `409`.

## 10. Tests

Backend test files:

```text
backend/tests/test_workflow_doctor.py
backend/tests/test_fix_suggestions.py
backend/tests/test_replay.py
```

Required backend coverage:

- diagnose missing provider key;
- diagnose missing agent config;
- diagnose invalid graph;
- diagnose unsafe API URL;
- diagnose read-only database tool violation;
- list suggestions tenant-scoped;
- viewer can read suggestions;
- viewer cannot apply;
- editor can apply safe patch;
- blocked patch path returns `422`;
- cross-tenant suggestion access returns `404`;
- replay validation passes for safe config;
- replay validation fails for invalid graph;
- apply and retry creates a new execution.

Frontend test files:

```text
frontend/src/api/fixSuggestions.test.js
frontend/src/hooks/useWorkflowDoctor.test.js
```

Required frontend coverage:

- API URL construction;
- diagnosis loading state;
- apply disabled for viewer;
- replay result rendering.

Smoke update:

- extend `scripts/smoke-backend.ps1` with one diagnosis path after a controlled failed execution.

## 11. Implementation Order

1. Add migration and models.
2. Add schemas.
3. Add diagnosis service with rule detectors.
4. Add API routes.
5. Add backend tests.
6. Add replay validation service.
7. Add apply patch service.
8. Add frontend API client and hook.
9. Add Doctor UI panel.
10. Extend smoke script.
11. Run full verification.

## 12. Acceptance Criteria

M8 is accepted when:

- backend tests pass;
- frontend tests/build pass;
- backend lint passes;
- Docker production smoke passes;
- a failed execution can be diagnosed from UI;
- at least 8 detector codes are implemented;
- suggestions never expose raw secrets;
- supported patches are previewed and applied transactionally;
- replay validation does not execute external side effects;
- apply and retry creates a new execution.

## 13. Non-Goals

- No autonomous patch application without user approval.
- No raw secret generation.
- No external API replay in MVP.
- No automatic paid-provider LLM diagnosis in MVP.
- No multi-tenant shared repair model.
