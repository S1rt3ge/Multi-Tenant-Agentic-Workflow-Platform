# M12 Progress: Operator-Grade Dispatch Controls

Date: 2026-05-17
Status: slice 27 green

## Completed

- Created M12 idea document.
- Created M12 dispatch controls spec.
- Created M12 TDD start checklist.
- Added failing M12 dispatch control API tests first.
- Added `POST /api/v1/executions/{execution_id}/retry`.
- Added `retry_dead_letter_execution` service behavior.
- Manual retry now creates a new pending execution with lineage metadata.
- Source dead-lettered execution remains failed and auditable.
- Added Slice 2 frontend red tests for retry helper and dispatch queue action.
- Added `retryExecution` frontend API helper.
- Added dead-letter retry action wiring in connector workspace.
- Retry action now appears only for editable dead-letter dispatch executions.
- Retry action queues the backend retry and refreshes the connector workspace.
- Added workflow dispatch pause/resume API.
- Added durable workflow dispatch pause state.
- Added dispatcher pause skip behavior for webhook-triggered pending executions.
- Added M12 workflow dispatch control tests.

## Current Slice

Slice 1 target:

- backend manual retry API for dead-lettered webhook executions: done;
- owner/editor only: done;
- preserve source failed execution: done;
- create a new pending retry execution: done;
- no frontend changes yet: preserved.

Slice 2 target:

- add connector workspace retry action for dead-letter executions: done;
- keep action hidden for viewers: done;
- call existing backend retry endpoint: done;
- refresh dispatch queue after retry: done;
- do not expose webhook payloads or headers: preserved.

Slice 3 target:

- add workflow-level webhook dispatch pause/resume API: done;
- persist pause state on workflow rows: done;
- require owner/editor role: done;
- keep tenant isolation: done;
- make dispatcher skip pending webhook executions for paused workflows: done;
- no frontend UI yet: preserved.

Slice 4 target:

- add trigger-level webhook rate limits: done;
- reject over-limit webhook ingestion with `429`: done;
- avoid creating executions for rate-limited requests: done;
- add dispatch queue filter controls: done;
- keep raw webhook payloads and headers out of UI: preserved.

Slice 5 target:

- add tenant-scoped dispatch health analytics endpoint: done;
- report paused workflows and currently throttled triggers: done;
- report pending, deferred retry, dead-letter, and manual retry dispatch counts: done;
- render dashboard dispatch health metrics and alerts: done;
- keep webhook payloads and headers out of analytics and UI: preserved.

Slice 6 target:

- add tenant-scoped dispatch alert routing policy: done;
- allow owner/editor policy update and block viewers: done;
- add dry-run preview for planned notification routes: done;
- render alert routing policy and preview on dashboard: done;
- send no external notifications and store no channel secrets: preserved.

Slice 7 target:

- add encrypted webhook alert channel credentials: done;
- add real delivery endpoint for credential-backed policy channels: done;
- add sanitized delivery audit log: done;
- show delivery channels and audit on dashboard: done;
- mock outbound HTTP in tests; no real external messages sent during verification: preserved.

Slice 8 target:

- add config-gated scheduled dispatch alert evaluation worker: done;
- enforce alert policy cooldown per channel and alert code: done;
- suppress duplicate delivery attempts without writing audit noise: done;
- keep worker reports and audit rows free of payloads, headers, and secrets.

Slice 9 target:

- add tenant-scoped dispatch runbook endpoint: done;
- add sanitized markdown handoff export: done;
- add frontend helper and dashboard handoff panel: done;
- keep runbook generation read-only and free of payloads, headers, workflow definitions, and secrets.

Slice 10 target:

- add tenant-scoped dispatch incident acknowledgement persistence: done;
- allow owner/editor to take ownership of the active dispatch incident: done;
- include sanitized acknowledgement state in the runbook and dashboard: done;
- keep acknowledgement APIs/UI free of payloads, headers, workflow definitions, encrypted config, and secrets.

Slice 11 target:

- resolve current acknowledged dispatch incident with sanitized review note: done;
- list tenant-scoped incident history for post-incident review: done;
- update dashboard runbook panel with resolve action and recent history: done;
- keep resolution/history APIs/UI free of payloads, headers, workflow definitions, encrypted config, and secrets: preserved.

Slice 12 target:

- report tenant-scoped incident totals, SLA breaches, and average resolution time: backend done;
- zero-fill daily incident trends for the requested window: backend done;
- group incident analytics by severity: backend done;
- render dashboard incident analytics without notes, identities, payloads, headers, workflow definitions, encrypted config, or secrets: done.

Slice 13 target:

- generate dry-run dispatch control automation recommendations from health, policy, and SLA signals: done;
- keep recommendations tenant-scoped and free of notes, identities, payloads, headers, workflow definitions, encrypted config, credential targets, and secrets: done;
- render dashboard automation recommendations without mutating dispatch state: done.

Slice 14 target:

- materialize current dispatch automation recommendations into approval-gated plans: done;
- enforce owner/editor create and owner-only approve/reject: done;
- keep plan approval/rejection dry-run without mutating dispatch state or sending notifications: done;
- keep plan responses tenant-scoped and free of notes, payloads, headers, workflow definitions, encrypted config, credential targets, notification secrets, and raw automation payloads: done.

Slice 15 target:

- worker claims only approved automation plans: done;
- approved `resume_guard` plans safely resume tenant paused workflow dispatch when current health is safe: done;
- unsupported and unsafe plans are blocked with sanitized execution results: done;
- terminal plans are idempotent and are not picked up again: done.

Slice 16 target:

- execute approved `approval_gated_retry` plans by creating one pending retry execution for an eligible tenant dead-lettered webhook execution: done;
- preserve manual retry lineage and source audit history: done;
- block retry plans with no eligible source: done;
- skip dead-letter sources that already have a retry child: done;
- keep worker results free of payloads, headers, workflow definitions, encrypted config, credential targets, notification secrets, and raw automation payloads: done.

Slice 17 target:

- add frontend automation plan API helpers: done;
- load automation plans into dashboard state with recommendations: done;
- allow eligible operators to create approval plans from recommendations: done;
- allow owners to approve/reject pending plans: done;
- render automation plan execution history without notes, identities, payloads, headers, workflow definitions, encrypted config, credential targets, notification secrets, or raw automation payloads: done.

Slice 18 target:

- add owner-only backend endpoint to run dispatch automation worker once: done;
- return only worker aggregate counts: done;
- add frontend worker run helper and guarded dashboard button: done;
- refresh automation plan history after manual worker runs: done;
- keep run responses/UI free of execution results, identities, payloads, headers, workflow definitions, encrypted config, credential targets, notification secrets, and raw automation payloads: done.

Slice 19 target:

- add tenant-scoped automation worker schedule config: done;
- add owner-only schedule config update API with validation: done;
- add durable manual worker run audit rows: done;
- expose tenant-scoped sanitized worker run audit list: done;
- render schedule config and recent run audit in dashboard with owner-only mutation controls: done.

Slice 20 target:

- add globally config-gated in-process automation scheduler loop: done;
- run only tenants with enabled worker config: done;
- enforce tenant `interval_minutes` using scheduled audit history: done;
- execute approved plans with tenant `max_plans_per_run`: done;
- write scheduled audit rows and sanitize scheduler-level failures: done.

Slice 21 target:

- acquire scheduler-level leader lock before tenant scan: done;
- skip without mutation when leader lock is unavailable: done;
- release leader lock after success: done;
- release leader lock after scheduler-level tenant failure: done;
- use PostgreSQL advisory locks with SQLite acquired fallback: done.

Slice 22 target:

- make scheduler due execution limit independent from skipped tenants: done;
- continue scanning past disabled/not-due/backoff tenants: done;
- add tenant-level failure backoff from scheduled audit history: done;
- report backoff skips separately from interval skips: done;
- preserve tenant isolation and sanitized reports: done.

Slice 23 target:

- add owner-only scheduler diagnostics endpoint: done;
- report global scheduler settings and tenant worker config: done;
- report approved plan backlog and latest scheduled audit: done;
- report tenant due/backoff/interval state: done;
- keep diagnostics read-only and sanitized: done.

Slice 24 target:

- add frontend helper for scheduler diagnostics: done;
- load owner-only diagnostics into dashboard state without breaking non-owner dashboard loads: done;
- render owner dashboard diagnostics for scheduler readiness/backlog/latest scheduled audit: done;
- keep diagnostics panel read-only and sanitized: done;
- hide diagnostics panel for viewer/editor roles: done.

Slice 25 target:

- add an internal read-only scheduler fleet snapshot service: done;
- report global scheduler metadata and aggregate tenant readiness counts: done;
- report approved automation backlog across tenants without executing plans: done;
- support aggregate-only mode without per-tenant summaries: done;
- keep the slice backend/internal only until a platform-admin authorization model exists: preserved.

Slice 26 target:

- add explicit platform-admin authorization guard: done;
- expose read-only scheduler fleet diagnostics API for platform admins: done;
- block tenant owner/editor/viewer users from cross-tenant fleet diagnostics: done;
- support aggregate-only fleet response with `include_tenants=false`: done;
- keep response sanitized and avoid frontend UI until the backend authorization surface is green: preserved.

Slice 27 target:

- add frontend scheduler fleet diagnostics helper: done;
- load fleet diagnostics only for platform-admin dashboards: done;
- render read-only platform-admin fleet panel: done;
- hide fleet panel for tenant-local owner/editor/viewer roles: done;
- keep fleet UI sanitized and free of mutation controls: done.

## Passing Checks

- `python -m pytest tests/test_execution_dispatch_controls.py -q` - `4 passed`.
- `python -m pytest tests/test_webhook_dispatcher.py tests/test_webhook_dispatcher_worker.py tests/test_connector_runtime.py -q` - `24 passed`.
- `python -m ruff check app tests alembic` - passed.
- `python -m pytest -q` - `315 passed`.
- `npm test -- executions.test.js DispatchQueuePanel.test.jsx ConnectorWorkspacePanel.test.jsx` - `13 passed`.
- `npm test` - `36 passed`.
- `npm run build` - passed.
- `npm audit --audit-level=high` - `found 0 vulnerabilities`.
- `python -m pytest tests/test_workflow_dispatch_controls.py -q` - `4 passed`.
- `python -m pytest tests/test_execution_dispatch_controls.py tests/test_workflow_dispatch_controls.py tests/test_webhook_dispatcher.py tests/test_webhook_dispatcher_worker.py tests/test_connector_runtime.py -q` - `32 passed`.
- `python -m pytest -q` - `319 passed`.
- `python -m pytest tests/test_connector_runtime.py -q` - `13 passed`.
- `python -m pytest tests/test_execution_dispatch_controls.py tests/test_workflow_dispatch_controls.py tests/test_webhook_dispatcher.py tests/test_webhook_dispatcher_worker.py tests/test_connector_runtime.py -q` - `34 passed`.
- `python -m ruff check app tests alembic` - passed.
- `python -m pytest -q` - `321 passed`.
- `npm test -- executions.test.js DispatchQueuePanel.test.jsx` - `12 passed`.
- `npm test -- executions.test.js DispatchQueuePanel.test.jsx ConnectorWorkspacePanel.test.jsx` - `15 passed`.
- `npm test` - `38 passed`.
- `npm run build` - passed.
- `npm audit --audit-level=high` - `found 0 vulnerabilities`.
- `python -m pytest tests/test_analytics.py -q` - `32 passed`.
- `python -m pytest tests/test_analytics.py tests/test_execution_dispatch_controls.py tests/test_workflow_dispatch_controls.py tests/test_webhook_dispatcher.py tests/test_webhook_dispatcher_worker.py tests/test_connector_runtime.py -q` - `66 passed`.
- `python -m ruff check app tests alembic` - passed.
- `python -m pytest -q` - `325 passed`.
- `npm test -- analytics.test.js DispatchHealthPanel.test.jsx` - `5 passed`.
- `npm test -- analytics.test.js DispatchHealthPanel.test.jsx executions.test.js DispatchQueuePanel.test.jsx ConnectorWorkspacePanel.test.jsx` - `20 passed`.
- `npm test` - `43 passed`.
- `npm run build` - passed.
- `npm audit --audit-level=high` - `found 0 vulnerabilities`.
- `python -m pytest tests/test_dispatch_alert_policy.py -q` - `5 passed`.
- `python -m pytest tests/test_analytics.py tests/test_dispatch_alert_policy.py tests/test_execution_dispatch_controls.py tests/test_workflow_dispatch_controls.py tests/test_webhook_dispatcher.py tests/test_webhook_dispatcher_worker.py tests/test_connector_runtime.py -q` - `71 passed`.
- `python -m ruff check app tests alembic` - passed.
- `python -m pytest -q` - `330 passed`.
- `npm test -- analytics.test.js DispatchAlertPolicyPanel.test.jsx` - `8 passed`.
- `npm test -- analytics.test.js DispatchAlertPolicyPanel.test.jsx DispatchHealthPanel.test.jsx executions.test.js DispatchQueuePanel.test.jsx ConnectorWorkspacePanel.test.jsx` - `26 passed`.
- `npm test` - `49 passed`.
- `npm run build` - passed.
- `npm audit --audit-level=high` - `found 0 vulnerabilities`.
- `python -m pytest tests/test_dispatch_alert_delivery.py -q` - `5 passed`.
- `npm test -- analytics.test.js DispatchAlertDeliveryPanel.test.jsx` - `10 passed`.
- `python -m pytest tests/test_analytics.py tests/test_dispatch_alert_delivery.py tests/test_dispatch_alert_policy.py tests/test_execution_dispatch_controls.py tests/test_workflow_dispatch_controls.py tests/test_webhook_dispatcher.py tests/test_webhook_dispatcher_worker.py tests/test_connector_runtime.py -q` - passed.
- `npm test -- analytics.test.js connectors.test.js DispatchAlertDeliveryPanel.test.jsx DispatchAlertPolicyPanel.test.jsx DispatchHealthPanel.test.jsx executions.test.js` - `31 passed`.
- `python -m ruff check app tests alembic` - passed.
- `python -m pytest -q` - `335 passed`.
- `npm test` - `54 passed`.
- `npm run build` - passed.
- local secret scan across `backend/app`, `frontend/src`, and `docs` - no unexpected real secrets found; matches were auth field names, environment-key wiring, or test/doc placeholders.
- `python -m pytest tests/test_dispatch_alert_evaluator_worker.py -q` - `8 passed`.
- `python -m pytest tests/test_dispatch_alert_delivery.py -q` - `5 passed`.
- `python -m pytest tests/test_analytics.py tests/test_dispatch_alert_delivery.py tests/test_dispatch_alert_evaluator_worker.py tests/test_dispatch_alert_policy.py tests/test_execution_dispatch_controls.py tests/test_workflow_dispatch_controls.py tests/test_webhook_dispatcher.py tests/test_webhook_dispatcher_worker.py tests/test_connector_runtime.py -q` - `84 passed`.
- `python -m ruff check app tests alembic` - passed.
- `python -m pytest -q` - `343 passed`.
- `npm test` - `54 passed`.
- `npm run build` - passed.
- local secret scan across `backend/app`, `frontend/src`, and `docs` - no unexpected real secrets found; matches were auth field names, environment-key wiring, or test/doc placeholders.
- `python -m pytest tests/test_dispatch_runbook.py -q` - `5 passed`.
- `npm test -- analytics.test.js DispatchRunbookPanel.test.jsx` - `10 passed`.
- `python -m pytest tests/test_analytics.py tests/test_dispatch_alert_delivery.py tests/test_dispatch_alert_evaluator_worker.py tests/test_dispatch_alert_policy.py tests/test_dispatch_runbook.py tests/test_execution_dispatch_controls.py tests/test_workflow_dispatch_controls.py tests/test_webhook_dispatcher.py tests/test_webhook_dispatcher_worker.py tests/test_connector_runtime.py -q` - `89 passed`.
- `npm test -- analytics.test.js DispatchRunbookPanel.test.jsx DispatchAlertDeliveryPanel.test.jsx DispatchAlertPolicyPanel.test.jsx DispatchHealthPanel.test.jsx` - `19 passed`.
- `python -m ruff check app tests alembic` - passed.
- `python -m pytest -q` - `348 passed`.
- `npm test` - `57 passed`.
- `npm run build` - passed.
- local secret scan across `backend/app`, `frontend/src`, and `docs` - no unexpected real secrets found; matches were auth field names, environment-key wiring, or test/doc placeholders.
- `python -m pytest tests/test_dispatch_incident_acknowledgement.py -q` - `6 passed`.
- `npm test -- analytics.test.js DispatchRunbookPanel.test.jsx` - `11 passed`.
- `python -m pytest tests/test_analytics.py tests/test_dispatch_alert_delivery.py tests/test_dispatch_alert_evaluator_worker.py tests/test_dispatch_alert_policy.py tests/test_dispatch_incident_acknowledgement.py tests/test_dispatch_runbook.py tests/test_execution_dispatch_controls.py tests/test_workflow_dispatch_controls.py tests/test_webhook_dispatcher.py tests/test_webhook_dispatcher_worker.py tests/test_connector_runtime.py -q` - `95 passed`.
- `npm test -- analytics.test.js DispatchRunbookPanel.test.jsx DispatchAlertDeliveryPanel.test.jsx DispatchAlertPolicyPanel.test.jsx DispatchHealthPanel.test.jsx` - `20 passed`.
- `python -m ruff check app tests alembic` - passed.
- `python -m pytest -q` - `354 passed`.
- `npm test` - `58 passed`.
- `npm run build` - passed.
- `python -m pytest tests/test_dispatch_incident_resolution.py -q` - `4 passed`.
- `npm test -- analytics.test.js DispatchRunbookPanel.test.jsx` - `12 passed`.
- `python -m pytest tests/test_analytics.py tests/test_dispatch_alert_delivery.py tests/test_dispatch_alert_evaluator_worker.py tests/test_dispatch_alert_policy.py tests/test_dispatch_incident_acknowledgement.py tests/test_dispatch_incident_resolution.py tests/test_dispatch_runbook.py tests/test_execution_dispatch_controls.py tests/test_workflow_dispatch_controls.py tests/test_webhook_dispatcher.py tests/test_webhook_dispatcher_worker.py tests/test_connector_runtime.py -q` - `99 passed`.
- `npm test -- analytics.test.js DispatchRunbookPanel.test.jsx DispatchAlertDeliveryPanel.test.jsx DispatchAlertPolicyPanel.test.jsx DispatchHealthPanel.test.jsx` - `21 passed`.
- `python -m ruff check app tests alembic` - passed.
- `python -m pytest -q` - `358 passed`.
- `npm test` - `59 passed`.
- `npm run build` - passed.
- Local secret scan across `backend/app`, `frontend/src`, and `docs` found no unexpected real secrets; remaining matches are test placeholders, auth field names, documented fake bearer strings, or env-key wiring.
- `python -m pytest tests/test_dispatch_incident_analytics.py -q` - `2 passed`.
- `python -m ruff check app tests alembic` - passed.
- `python -m pytest tests/test_analytics.py tests/test_dispatch_alert_delivery.py tests/test_dispatch_alert_evaluator_worker.py tests/test_dispatch_alert_policy.py tests/test_dispatch_incident_acknowledgement.py tests/test_dispatch_incident_resolution.py tests/test_dispatch_incident_analytics.py tests/test_dispatch_runbook.py tests/test_execution_dispatch_controls.py tests/test_workflow_dispatch_controls.py tests/test_webhook_dispatcher.py tests/test_webhook_dispatcher_worker.py tests/test_connector_runtime.py -q` - `101 passed`.
- `python -m pytest -q` - `360 passed`.
- `npm test -- analytics.test.js DispatchIncidentAnalyticsPanel.test.jsx` - `12 passed`.
- `npm run build` - passed.
- `npm test` - `61 passed`.
- Local post-Slice 12 secret scan found no unexpected real secrets; remaining matches are test placeholders, auth field names, documented fake bearer strings, or env-key wiring.
- `python -m pytest tests/test_dispatch_control_recommendations.py -q` - `2 passed`.
- `npm test -- analytics.test.js DispatchAutomationRecommendationsPanel.test.jsx` - `13 passed`.
- `python -m ruff check app tests alembic` - passed.
- `python -m pytest tests/test_analytics.py tests/test_dispatch_alert_delivery.py tests/test_dispatch_alert_evaluator_worker.py tests/test_dispatch_alert_policy.py tests/test_dispatch_incident_acknowledgement.py tests/test_dispatch_incident_resolution.py tests/test_dispatch_incident_analytics.py tests/test_dispatch_control_recommendations.py tests/test_dispatch_runbook.py tests/test_execution_dispatch_controls.py tests/test_workflow_dispatch_controls.py tests/test_webhook_dispatcher.py tests/test_webhook_dispatcher_worker.py tests/test_connector_runtime.py -q` - `103 passed`.
- `npm test` - `63 passed`.
- `python -m pytest -q` - `362 passed`.
- `npm run build` - passed.
- Local post-Slice 13 secret scan found no unexpected real secrets; remaining matches are test placeholders, auth field names, documented fake bearer strings, or env-key wiring.
- `python -m pytest tests/test_dispatch_automation_plans.py -q` - `4 passed`.
- `python -m ruff check app tests alembic` - passed.
- `python -m pytest tests/test_analytics.py tests/test_dispatch_alert_delivery.py tests/test_dispatch_alert_evaluator_worker.py tests/test_dispatch_alert_policy.py tests/test_dispatch_incident_acknowledgement.py tests/test_dispatch_incident_resolution.py tests/test_dispatch_incident_analytics.py tests/test_dispatch_control_recommendations.py tests/test_dispatch_automation_plans.py tests/test_dispatch_runbook.py tests/test_execution_dispatch_controls.py tests/test_workflow_dispatch_controls.py tests/test_webhook_dispatcher.py tests/test_webhook_dispatcher_worker.py tests/test_connector_runtime.py -q` - `107 passed`.
- `python -m pytest -q` - `366 passed`.
- Local post-Slice 14 secret scan found no unexpected real secrets; remaining matches are test placeholders, auth field names, documented fake bearer strings, or env-key wiring.
- `python -m pytest tests/test_dispatch_automation_plan_worker.py -q` - `3 passed`.
- `python -m ruff check app tests alembic` - passed.
- `python -m pytest tests/test_analytics.py tests/test_dispatch_alert_delivery.py tests/test_dispatch_alert_evaluator_worker.py tests/test_dispatch_alert_policy.py tests/test_dispatch_incident_acknowledgement.py tests/test_dispatch_incident_resolution.py tests/test_dispatch_incident_analytics.py tests/test_dispatch_control_recommendations.py tests/test_dispatch_automation_plans.py tests/test_dispatch_automation_plan_worker.py tests/test_dispatch_runbook.py tests/test_execution_dispatch_controls.py tests/test_workflow_dispatch_controls.py tests/test_webhook_dispatcher.py tests/test_webhook_dispatcher_worker.py tests/test_connector_runtime.py -q` - `110 passed`.
- `python -m pytest -q` - `369 passed`.
- Local post-Slice 15 secret scan found no unexpected real secrets; remaining matches are test placeholders, auth field names, documented fake bearer strings, or env-key wiring.
- `python -m pytest tests/test_dispatch_automation_plan_worker.py -q` - `6 passed`.
- `python -m ruff check app tests alembic` - passed.
- `python -m pytest tests/test_analytics.py tests/test_dispatch_alert_delivery.py tests/test_dispatch_alert_evaluator_worker.py tests/test_dispatch_alert_policy.py tests/test_dispatch_incident_acknowledgement.py tests/test_dispatch_incident_resolution.py tests/test_dispatch_incident_analytics.py tests/test_dispatch_control_recommendations.py tests/test_dispatch_automation_plans.py tests/test_dispatch_automation_plan_worker.py tests/test_dispatch_runbook.py tests/test_execution_dispatch_controls.py tests/test_workflow_dispatch_controls.py tests/test_webhook_dispatcher.py tests/test_webhook_dispatcher_worker.py tests/test_connector_runtime.py -q` - `113 passed`.
- `python -m pytest -q` - `372 passed`.
- Local post-Slice 16 secret scan across changed worker/docs files found no secret-like matches.
- `npm test -- analytics.test.js DispatchAutomationRecommendationsPanel.test.jsx` - `17 passed`.
- `npm test` - `67 passed`.
- `npm run build` - passed.
- `python -m ruff check app tests alembic` - passed.
- `python -m pytest tests/test_dispatch_automation_plans.py tests/test_dispatch_automation_plan_worker.py tests/test_dispatch_control_recommendations.py -q` - `12 passed`.
- `python -m pytest tests/test_analytics.py tests/test_dispatch_alert_delivery.py tests/test_dispatch_alert_evaluator_worker.py tests/test_dispatch_alert_policy.py tests/test_dispatch_incident_acknowledgement.py tests/test_dispatch_incident_resolution.py tests/test_dispatch_incident_analytics.py tests/test_dispatch_control_recommendations.py tests/test_dispatch_automation_plans.py tests/test_dispatch_automation_plan_worker.py tests/test_dispatch_runbook.py tests/test_execution_dispatch_controls.py tests/test_workflow_dispatch_controls.py tests/test_webhook_dispatcher.py tests/test_webhook_dispatcher_worker.py tests/test_connector_runtime.py -q` - `113 passed`.
- Local post-Slice 17 secret scan across changed frontend/docs files found only test placeholders and existing budget-token wording.
- `python -m pytest tests/test_dispatch_automation_plans.py -q` - `6 passed`.
- `npm test -- analytics.test.js DispatchAutomationRecommendationsPanel.test.jsx` - `18 passed`.
- `npm test` - `68 passed`.
- `python -m ruff check app tests alembic` - passed.
- `python -m pytest tests/test_dispatch_automation_plans.py tests/test_dispatch_automation_plan_worker.py tests/test_dispatch_control_recommendations.py -q` - passed.
- `npm run build` - passed.
- `python -m pytest tests/test_analytics.py tests/test_dispatch_alert_delivery.py tests/test_dispatch_alert_evaluator_worker.py tests/test_dispatch_alert_policy.py tests/test_dispatch_incident_acknowledgement.py tests/test_dispatch_incident_resolution.py tests/test_dispatch_incident_analytics.py tests/test_dispatch_control_recommendations.py tests/test_dispatch_automation_plans.py tests/test_dispatch_automation_plan_worker.py tests/test_dispatch_runbook.py tests/test_execution_dispatch_controls.py tests/test_workflow_dispatch_controls.py tests/test_webhook_dispatcher.py tests/test_webhook_dispatcher_worker.py tests/test_connector_runtime.py -q` - `115 passed`.
- Local post-Slice 18 secret scan across changed files found only test placeholders, existing auth-token fixtures, and budget-token wording.
- `python -m pytest tests/test_dispatch_automation_plans.py -q` - `8 passed`.
- `python -m pytest tests/test_dispatch_automation_plans.py tests/test_dispatch_automation_plan_worker.py tests/test_dispatch_control_recommendations.py -q` - `16 passed`.
- `npm test -- analytics.test.js DispatchAutomationRecommendationsPanel.test.jsx` - `20 passed`.
- `python -m ruff check app tests alembic` - passed.
- M12 backend regression suite - passed; `117 tests collected`.
- `npm test` - `70 passed`.
- `npm run build` - passed.
- `python -m pytest -q` - `376 passed`.
- Local post-Slice 19 secret scan across `backend/app`, `frontend/src`, and M12 docs found no unexpected real secrets; remaining matches are existing auth/token field names, fake test placeholders, and security-rule wording.
- `python -m pytest tests/test_dispatch_automation_worker_scheduler.py -q` - `9 passed`.
- `python -m pytest tests/test_dispatch_automation_worker_scheduler.py tests/test_dispatch_automation_plans.py tests/test_dispatch_automation_plan_worker.py tests/test_dispatch_control_recommendations.py -q` - `25 passed`.
- `python -m ruff check app tests alembic` - passed.
- M12 backend regression suite including scheduler - `126 passed`.
- `python -m pytest -q` - `385 passed`.
- `python -m pytest tests/test_dispatch_automation_worker_scheduler.py -q` - `12 passed`.
- `python -m pytest tests/test_dispatch_automation_worker_scheduler.py tests/test_dispatch_automation_plans.py tests/test_dispatch_automation_plan_worker.py tests/test_dispatch_control_recommendations.py -q` - `28 passed`.
- `python -m ruff check app tests alembic` - passed.
- M12 backend regression suite including scheduler leader lock - `129 passed`.
- `python -m pytest -q` - `388 passed`.
- `python -m pytest tests/test_dispatch_automation_worker_scheduler.py -q` - `14 passed`.
- `python -m pytest tests/test_dispatch_automation_worker_scheduler.py tests/test_dispatch_automation_plans.py tests/test_dispatch_automation_plan_worker.py tests/test_dispatch_control_recommendations.py -q` - `30 passed`.
- `python -m ruff check app tests alembic` - passed.
- M12 backend regression suite including scheduler fairness/backoff - `131 passed`.
- `python -m pytest -q` - `390 passed`.
- `python -m pytest tests/test_dispatch_automation_plans.py -q` - `11 passed`.
- `python -m pytest tests/test_dispatch_automation_plans.py tests/test_dispatch_automation_worker_scheduler.py tests/test_dispatch_automation_plan_worker.py tests/test_dispatch_control_recommendations.py -q` - `33 passed`.
- `python -m ruff check app tests alembic` - passed.
- M12 backend regression suite including scheduler diagnostics - `134 passed`.
- `python -m pytest -q` - passed with exit code 0.
- `npm test -- analytics.test.js DispatchSchedulerDiagnosticsPanel.test.jsx` - `21 passed`.
- `npm test -- analytics.test.js DispatchSchedulerDiagnosticsPanel.test.jsx DispatchAutomationRecommendationsPanel.test.jsx DispatchHealthPanel.test.jsx` - `27 passed`.
- `npm test` - `74 passed`.
- `npm run build` - passed.
- `python -m pytest tests/test_dispatch_automation_plans.py -q` - `11 passed`.
- `python -m ruff check app tests alembic` - passed.
- Local Slice 24 secret scan found no unexpected real secrets; remaining matches are test placeholders, budget-token wording, and security-rule text.
- `python -m pytest tests/test_dispatch_automation_worker_scheduler.py -q` - `16 passed`.
- `python -m pytest tests/test_dispatch_automation_worker_scheduler.py tests/test_dispatch_automation_plans.py tests/test_dispatch_automation_plan_worker.py tests/test_dispatch_control_recommendations.py -q` - `35 passed`.
- `python -m ruff check app tests alembic` - passed.
- M12 backend regression suite including internal scheduler fleet snapshot - `136 passed`.
- `python -m pytest -q` - `395 passed`.
- Local Slice 25 secret scan found no unexpected real secrets; remaining matches are test fixtures and security-rule wording.
- `python -m pytest tests/test_dispatch_automation_plans.py -q` - `14 passed`.
- `python -m pytest tests/test_dispatch_automation_plans.py tests/test_dispatch_automation_worker_scheduler.py tests/test_auth.py -q` - `55 passed`.
- `python -m ruff check app tests alembic` - passed.
- M12 backend regression suite including platform-admin fleet diagnostics - `139 passed`.
- `python -m pytest -q` - `398 passed`.
- Local Slice 26 secret scan found no unexpected real secrets; remaining matches are test fixtures, existing auth field names, and security-rule wording.
- `npm test -- analytics.test.js DispatchSchedulerFleetPanel.test.jsx` - `23 passed`.
- `npm test -- analytics.test.js DispatchSchedulerFleetPanel.test.jsx DispatchSchedulerDiagnosticsPanel.test.jsx DispatchAutomationRecommendationsPanel.test.jsx DispatchHealthPanel.test.jsx` - `32 passed`.
- `npm test` - `79 passed`.
- `python -m pytest tests/test_dispatch_automation_plans.py tests/test_dispatch_automation_worker_scheduler.py -q` - `30 passed`.
- `npm run build` - passed.
- Local Slice 27 secret scan found no unexpected real secrets; remaining matches are synthetic test fixtures, existing documented fields, and security-rule wording.

## Pending

- `npm audit --audit-level=high` was blocked by external-action policy because it sends dependency metadata to the public npm service; requires explicit approval before running.
