# Heavy Platform Mechanisms - Spec-First Implementation Plan

## 1. PROJECT_IDEA

GraphPilot should evolve from a visual agent workflow runner into a production-grade automation and orchestration platform: something that can connect to real systems, run long-lived workflows reliably, validate data contracts, simulate changes before deployment, package reusable automation modules, and enforce security and approval policy.

The product direction is: n8n-style automation, but with agentic execution, schema-aware workflow safety, replayable self-healing, and enterprise-grade control surfaces.

The heavy mechanisms are:

1. Connector Runtime and Trigger System
2. Durable Execution Engine
3. Typed Data Contracts Between Nodes
4. Workflow Simulation and Test Lab
5. Workflow Packages and Subflows
6. Policy, Approval, and Governance Engine

M8 Workflow Doctor is already the first self-healing layer. The next milestones should make Doctor more valuable because it will diagnose real connectors, typed contract failures, durable retries, replay failures, and policy blocks.

## 2. North Star Workflow

A user should eventually be able to build this kind of production workflow:

1. A GitHub issue, webhook, schedule, or Slack event triggers the workflow.
2. The workflow validates incoming data against a typed input contract.
3. Agent and connector nodes execute with durable checkpoints.
4. External actions use stored credentials, rate limits, retries, and idempotency.
5. Risky actions pause for approval.
6. A failed node can be diagnosed by Workflow Doctor.
7. A suggested patch can be replayed against fixtures.
8. The workflow can be packaged as a reusable subflow and installed in another workspace.

## 3. Milestone Order

Recommended build order:

| Milestone | Name | Why This Order |
| --- | --- | --- |
| M9 | Connector Runtime and Trigger System | Turns the platform into something that can connect to real tools and events. |
| M10 | Durable Execution Engine | Makes connected workflows reliable enough for production. |
| M11 | Typed Data Contracts | Makes large workflows understandable, validatable, and safer to change. |
| M12 | Workflow Simulation and Test Lab | Lets users test workflows before deploying changes. |
| M13 | Workflow Packages and Subflows | Enables reusable large mechanisms and internal workflow libraries. |
| M14 | Policy, Approval, and Governance Engine | Adds enterprise-grade control, compliance, and human checkpoints. |

Do not build these in parallel unless separate agents own disjoint layers. M9 should be the next implementation target.

## 4. M9 - Connector Runtime and Trigger System

### User Stories

- As a builder, I can add a connector action node, configure an action, and map workflow data into its inputs.
- As a builder, I can create webhook, schedule, and manual triggers.
- As an owner, I can store connector credentials without exposing secrets to logs or frontend responses.
- As an operator, I can see connector call status, latency, retries, and sanitized errors in execution logs.
- As a platform developer, I can add a new connector through a manifest and handler without changing the workflow engine core.

### Data Model

New tables:

- `connectors`
  - `id`, `key`, `name`, `description`, `version`, `manifest`, `is_active`, timestamps
- `connector_credentials`
  - `id`, `tenant_id`, `connector_key`, `name`, `encrypted_config`, `created_by`, timestamps
- `connector_actions`
  - `id`, `connector_key`, `action_key`, `schema`, `handler_type`, `is_active`
- `workflow_triggers`
  - `id`, `tenant_id`, `workflow_id`, `trigger_type`, `config`, `is_active`, timestamps
- `webhook_events`
  - `id`, `tenant_id`, `workflow_id`, `trigger_id`, `payload`, `headers_sanitized`, `status`, timestamps

Extend existing execution logs:

- Add `node_id`, `node_type`, `connector_key`, `action_key`, `attempt`, `retryable`, `sanitized_error`.

### API / Server Logic

Endpoints:

- `GET /api/v1/connectors`
- `GET /api/v1/connectors/{connector_key}`
- `GET /api/v1/connectors/{connector_key}/actions`
- `POST /api/v1/connector-credentials`
- `GET /api/v1/connector-credentials`
- `DELETE /api/v1/connector-credentials/{id}`
- `POST /api/v1/workflows/{workflow_id}/triggers`
- `GET /api/v1/workflows/{workflow_id}/triggers`
- `POST /api/v1/webhooks/{public_trigger_id}`
- `POST /api/v1/workflows/{workflow_id}/execute` should accept trigger context.

Server services:

- `connector_manifest_service`
- `credential_service`
- `connector_runtime_service`
- `trigger_service`
- `webhook_ingestion_service`

Runtime rules:

- Every connector action receives normalized input, credential reference, tenant context, and execution context.
- No connector handler receives raw user tokens unless explicitly requested through credential resolution.
- Connector errors must be sanitized before logs and API responses.
- Webhook triggers create executions through the same execution service path as manual runs.

### Screens / Components

- Connector library page
- Credential manager modal
- Builder node type: connector action
- Builder node type: trigger
- Action config panel
- Trigger config panel
- Execution log connector call detail

### Business Logic

- Manifest defines connector key, actions, inputs, outputs, auth type, rate limit hints, and retry defaults.
- Credentials are stored encrypted server-side.
- Frontend never receives secret values after creation.
- Action execution produces structured logs with request metadata, sanitized response summary, latency, and retry info.
- Webhook trigger validates tenant/workflow ownership through opaque public trigger id.

### Edge Cases

- Missing credential
- Revoked credential
- Invalid action input
- Connector action timeout
- Non-2xx HTTP response
- Rate limit response
- Webhook replay / duplicate event
- Secret accidentally included in connector output
- Disabled connector or disabled trigger
- Cross-tenant credential access attempt

### Acceptance Criteria

- A workflow can be triggered manually and through a webhook.
- A workflow can execute at least one built-in connector action.
- Credential values never appear in frontend responses or execution logs.
- Connector action failures are visible in logs and diagnosable by Workflow Doctor.
- Tests cover tenant isolation, secret redaction, missing credentials, webhook execution creation, and connector action success/failure.

## 5. M10 - Durable Execution Engine

### User Stories

- As an operator, I can resume a workflow after worker restart.
- As a builder, I can configure retries per node.
- As an operator, I can pause, resume, cancel, and inspect long-running executions.
- As a tenant owner, I can rely on concurrency limits and idempotency for external actions.

### Data Model

New tables:

- `execution_checkpoints`
- `execution_node_runs`
- `execution_locks`
- `execution_retry_policies`
- `dead_letter_executions`

Extend `executions`:

- `resume_token`, `current_node_id`, `attempt`, `locked_by`, `locked_until`, `idempotency_key`.

### API / Server Logic

Endpoints:

- `POST /api/v1/executions/{id}/resume`
- `POST /api/v1/executions/{id}/pause`
- `POST /api/v1/executions/{id}/retry-node`
- `GET /api/v1/executions/{id}/checkpoints`
- `GET /api/v1/dead-letter-executions`

Services:

- `durable_execution_service`
- `checkpoint_service`
- `execution_lock_service`
- `retry_policy_service`

### Screens / Components

- Execution timeline with node run attempts
- Retry policy editor in node config
- Dead-letter queue view
- Pause/resume controls
- Checkpoint inspector

### Business Logic

- Before every node run, persist node run status.
- After every node run, persist checkpoint output.
- On worker crash, execution can resume from last successful checkpoint.
- External connector actions use idempotency keys where supported.
- Retry policy supports fixed delay, exponential backoff, max attempts, and retryable error classes.

### Edge Cases

- Worker dies during connector action
- Duplicate worker picks same execution
- Retry limit exceeded
- Resume after workflow definition changed
- Pause requested while node is running
- Cancel requested during retry wait
- Dead-letter replay after partial external side effect

### Acceptance Criteria

- A failed worker does not lose execution progress.
- Duplicate workers cannot execute the same node concurrently.
- Retry state is visible in logs.
- Cancel and pause behavior is deterministic.
- Tests include simulated worker crash, lock expiry, retry exhaustion, and resume.

## 6. M11 - Typed Data Contracts Between Nodes

### User Stories

- As a builder, I can define input/output schemas for nodes.
- As a builder, I can see incompatible connections before running.
- As a builder, I can map fields between nodes with validation.
- As Workflow Doctor, the system can diagnose schema mismatches and suggest mapping fixes.

### Data Model

New tables:

- `node_contracts`
- `node_field_mappings`
- `contract_validation_results`

Extend workflow definition:

- Node metadata includes `input_contract_id`, `output_contract_id`, and mapping references.

### API / Server Logic

Endpoints:

- `POST /api/v1/workflows/{id}/nodes/{node_id}/contracts`
- `PUT /api/v1/workflows/{id}/nodes/{node_id}/mappings`
- `POST /api/v1/workflows/{id}/validate-contracts`

Services:

- `contract_schema_service`
- `mapping_validation_service`
- `contract_inference_service`

### Screens / Components

- Contract editor
- Field mapper
- Connection validation badges
- Schema mismatch panel
- Suggested mapping preview

### Business Logic

- Schemas should use JSON Schema subset initially.
- Node output schema can be explicit or inferred from sample executions.
- Connection validation checks source output compatibility with target input.
- Runtime validates node input before execution and node output after execution.

### Edge Cases

- Optional fields
- Arrays and nested objects
- Union-like values
- Agent output not valid JSON
- Connector output changes shape
- User edits workflow after mappings were created

### Acceptance Criteria

- Invalid node connections can be detected before execution.
- Runtime schema validation failure creates structured logs.
- Workflow Doctor can classify contract mismatch failures.
- Tests cover nested fields, missing required fields, invalid mappings, and inference fallback.

## 7. M12 - Workflow Simulation and Test Lab

### User Stories

- As a builder, I can create test fixtures for a workflow.
- As a builder, I can run a workflow in simulation mode without external side effects.
- As an operator, I can compare workflow versions against regression cases.
- As Workflow Doctor, I can replay a proposed fix against saved fixtures.

### Data Model

New tables:

- `workflow_test_suites`
- `workflow_test_cases`
- `workflow_test_runs`
- `workflow_mock_responses`
- `workflow_version_snapshots`

### API / Server Logic

Endpoints:

- `POST /api/v1/workflows/{id}/test-suites`
- `POST /api/v1/workflows/{id}/test-cases`
- `POST /api/v1/workflows/{id}/simulate`
- `GET /api/v1/workflows/{id}/test-runs`
- `POST /api/v1/workflows/{id}/compare-version`

Services:

- `simulation_service`
- `mock_connector_service`
- `workflow_snapshot_service`
- `test_assertion_service`

### Screens / Components

- Test Lab page
- Fixture editor
- Mock connector response editor
- Simulation run viewer
- Version comparison panel

### Business Logic

- Simulation mode blocks external connector side effects.
- Connector calls are mocked from fixtures or fail with explicit missing mock.
- Agent calls can be mocked, recorded, or real depending on mode.
- Assertions check final output, node outputs, logs, cost, and policy decisions.

### Edge Cases

- Missing mock response
- Non-deterministic agent output
- Fixture schema mismatch
- Workflow changed after test case was created
- Simulation accidentally attempts real external action

### Acceptance Criteria

- A workflow can run in simulation without external side effects.
- Test cases can pass/fail with clear assertions.
- Workflow Doctor replay can use simulation fixtures.
- Tests cover mock enforcement, failed assertions, and version snapshot replay.

## 8. M13 - Workflow Packages and Subflows

### User Stories

- As a builder, I can turn a workflow into a reusable subflow.
- As a builder, I can call a subflow from another workflow.
- As an owner, I can version and publish internal workflow packages.
- As a team, we can maintain reusable automation building blocks.

### Data Model

New tables:

- `workflow_packages`
- `workflow_package_versions`
- `workflow_subflow_calls`
- `workflow_package_installs`

Extend workflow definition:

- Node type `subflow_call`
- Inputs/outputs tied to M11 contracts.

### API / Server Logic

Endpoints:

- `POST /api/v1/workflows/{id}/publish-package`
- `GET /api/v1/workflow-packages`
- `POST /api/v1/workflow-packages/{id}/install`
- `POST /api/v1/subflows/{id}/execute`

Services:

- `package_service`
- `subflow_runtime_service`
- `workflow_dependency_service`

### Screens / Components

- Package library
- Publish workflow modal
- Subflow node config
- Dependency graph viewer
- Version upgrade diff

### Business Logic

- A package version is immutable.
- Subflows expose typed inputs and outputs.
- Parent execution creates child execution records.
- Package updates require explicit upgrade in consuming workflows.

### Edge Cases

- Recursive subflow calls
- Package deleted while installed
- Version mismatch
- Contract break between versions
- Parent cancelled while child subflow running

### Acceptance Criteria

- A workflow can call another workflow as a subflow.
- Package versions are immutable.
- Parent/child execution relationship is visible.
- Tests cover recursion guard, version pinning, and subflow failure propagation.

## 9. M14 - Policy, Approval, and Governance Engine

### User Stories

- As an owner, I can define policies for external actions, domains, cost, and data sensitivity.
- As an approver, I can approve or reject paused workflow actions.
- As an operator, I can audit who approved what and why.
- As a security reviewer, I can prove secrets and PII are controlled.

### Data Model

New tables:

- `policy_rules`
- `policy_evaluations`
- `approval_requests`
- `approval_decisions`
- `audit_events`

### API / Server Logic

Endpoints:

- `POST /api/v1/policies`
- `GET /api/v1/policies`
- `POST /api/v1/approval-requests/{id}/approve`
- `POST /api/v1/approval-requests/{id}/reject`
- `GET /api/v1/audit-events`

Services:

- `policy_engine_service`
- `approval_service`
- `audit_log_service`
- `pii_detection_service`

### Screens / Components

- Policy rules page
- Approval inbox
- Approval modal inside execution page
- Audit log explorer
- Policy evaluation details

### Business Logic

- Policy engine evaluates before connector calls, agent calls, subflow calls, and external output.
- Policies can block, allow, redact, or require approval.
- Approval requests pause durable execution.
- Every policy decision writes an audit event.

### Edge Cases

- Approver is same user who triggered execution
- Approval expires
- Policy changed while execution is paused
- Connector call contains PII
- Cost threshold exceeded mid-run
- External domain not on allowlist

### Acceptance Criteria

- Risky actions can pause execution for approval.
- Audit log includes policy decision, actor, timestamp, and sanitized context.
- Policy blocks are visible to Workflow Doctor.
- Tests cover allow/block/approval/redact decisions and tenant isolation.

## 10. Config Generator Layer

Create a compact generated build config before each milestone:

```yaml
milestone: M9 Connector Runtime
allowed_write_paths:
  - backend/app/models
  - backend/app/schemas
  - backend/app/services
  - backend/app/api/v1
  - backend/alembic/versions
  - backend/tests
  - frontend/src/api
  - frontend/src/hooks
  - frontend/src/components
  - frontend/src/pages
required_checks:
  - python -m ruff check app tests
  - python -m pytest tests/test_connector_runtime.py -q
  - python -m pytest -q
  - npm test
  - npm run build
security_rules:
  - never expose credential plaintext after creation
  - sanitize connector request and response logs
  - enforce tenant_id on every query
  - use explicit allowlists for patchable and callable surfaces
```

Every milestone should get its own generated config file under `docs/build-configs/` before implementation begins.

## 11. Subagent Plan

Use read-only reviewers by default. Do not let multiple agents edit the same files.

Recommended roles:

- `spec-writer`
  - Owns docs only.
  - Produces module spec with 6 blocks.
- `backend-worker`
  - Owns backend models, migrations, schemas, services, routes, backend tests.
- `frontend-worker`
  - Owns frontend API clients, hooks, components, pages, frontend tests.
- `security-reviewer`
  - Read-only.
  - Reviews secrets, tenant isolation, authz, SSRF, webhook risks, audit gaps.
- `qa-reviewer`
  - Read-only.
  - Reviews acceptance criteria, missing tests, edge-case coverage.

For Codex without external subagents, follow the same ownership mentally and do not mix stages in one messy change.

## 12. Prompt Instruction Layer

Use this implementation prompt for each milestone:

```text
Implement milestone M{N} using spec-first methodology.

Rules:
1. Read the milestone spec first.
2. Do not write code until tests are defined.
3. Keep edits scoped to the milestone write paths.
4. Add backend tests for service, API, tenant isolation, and failure cases.
5. Add frontend tests for API helpers and critical UI behavior.
6. Never expose secrets in API responses, logs, or frontend state.
7. Run required checks.
8. Summarize changed files, passing checks, and remaining risks.
```

## 13. Cross-Cutting Security Requirements

- Every table with tenant data must include `tenant_id`.
- Every query must filter by `tenant_id` unless it is a global public connector manifest.
- Credentials must be encrypted at rest.
- Webhook public ids must be opaque and unguessable.
- Connector logs must redact headers, query params, bodies, and nested secret-like keys.
- SSRF guard must block localhost, metadata IPs, private networks, and disallowed schemes for HTTP connectors.
- Approval and policy decisions must be immutable audit events.
- Workflow Doctor patches must remain allowlist-based.

## 14. Cross-Cutting Test Requirements

Each milestone needs:

- Unit tests for pure validation logic.
- Service tests for business rules.
- API tests for authorization and tenant isolation.
- Migration smoke check.
- Frontend API helper tests.
- At least one end-to-end or HTTP smoke for the main user journey.
- Security regression tests for secrets and cross-tenant access.

## 15. Recommended Next Action

Start M9 only.

Before code:

1. Create `docs/M9_CONNECTOR_RUNTIME_SPEC.md`.
2. Create `docs/build-configs/M9_CONNECTOR_RUNTIME.yaml`.
3. Write failing backend tests for:
   - connector manifest listing
   - credential create/list redaction
   - webhook trigger creates execution
   - connector action logs sanitized failure
   - cross-tenant credential access denied
4. Write frontend API helper tests for connectors and credentials.
5. Implement the minimum vertical slice:
   - HTTP connector action
   - webhook trigger
   - credential storage redaction
   - execution log integration
   - Doctor detector for missing credential

Do not start M10 until this vertical slice is green.
