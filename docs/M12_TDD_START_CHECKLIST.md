# M12 TDD Start Checklist

Date: 2026-05-17
Status: slice 27 green

## Red Tests To Add First

Manual dead-letter retry API:

- [x] editor can retry a dead-lettered webhook execution.
- [x] retry creates a new pending execution.
- [x] retry execution stores incremented attempt and lineage metadata.
- [x] source execution remains failed and dead-lettered.
- [x] non-dead-letter execution retry returns `409`.
- [x] viewer retry returns `403`.
- [x] cross-tenant retry returns `404`.

Regression:

- [x] M11 dispatcher tests remain green.
- [x] execution API tests remain green.

Connector workspace retry UI:

- [x] execution API helper posts to retry endpoint.
- [x] dispatch queue panel renders retry action for dead-letter executions.
- [x] dispatch queue panel hides retry action for non-dead-letter executions.
- [x] connector workspace passes retry action into dispatch queue.
- [x] retry UI does not render webhook payloads or headers.

Workflow dispatch pause/resume:

- [x] owner can pause workflow webhook dispatch.
- [x] owner can resume workflow webhook dispatch.
- [x] viewer pause/resume returns `403`.
- [x] cross-tenant pause/resume returns `404`.
- [x] dispatcher skips pending webhook executions when workflow dispatch is paused.
- [x] paused execution remains `pending`.

Trigger rate limits:

- [x] webhook trigger with enabled rate limit accepts requests up to the window limit.
- [x] webhook trigger with enabled rate limit returns `429` after the window limit.
- [x] rate-limited webhook request does not create a pending execution.
- [x] webhook trigger without enabled rate limit preserves existing ingest behavior.

Dispatch queue filtering:

- [x] dispatch queue API helper passes `status_filter` through to executions endpoint.
- [x] dispatch queue filter helper returns only matching webhook executions.
- [x] dispatch queue renders all, active, deferred, dead-letter, and completed filters.
- [x] filtered dispatch queue still hides non-webhook executions.
- [x] filtered dispatch queue still hides raw webhook payloads and headers.

Dispatch health metrics and alerts:

- [x] dispatch health endpoint returns paused workflow count.
- [x] dispatch health endpoint returns currently throttled trigger count.
- [x] dispatch health endpoint returns pending, deferred retry, dead-letter, and manual retry counts.
- [x] dispatch health endpoint is tenant-scoped.
- [x] dispatch health endpoint requires authentication.
- [x] dispatch health alerts do not include webhook payloads or headers.
- [x] frontend analytics helper fetches dispatch health metrics.
- [x] dashboard hook loads dispatch health with other analytics.
- [x] dashboard renders dispatch health metrics and alerts.
- [x] dashboard empty dispatch health renders without noisy alerts.

Alert routing policy and preview:

- [x] dispatch alert policy returns safe defaults.
- [x] owner/editor can update dispatch alert policy.
- [x] viewer cannot update dispatch alert policy.
- [x] dispatch alert policy is tenant-scoped.
- [x] dispatch alert policy preview returns matched alerts and planned routes.
- [x] dispatch alert policy preview is dry-run only.
- [x] dispatch alert policy preview does not expose payloads, headers, or secrets.
- [x] frontend analytics helpers read, update, and preview dispatch alert policy.
- [x] dashboard renders alert routing policy and preview.

Notification delivery adapters and audit logs:

- [x] owner/editor can create encrypted webhook alert channel credentials.
- [x] viewer cannot create alert channel credentials.
- [x] channel list returns previews without encrypted config or raw secrets.
- [x] private webhook URLs are rejected.
- [x] delivery endpoint sends matched alerts to credential-backed policy channels.
- [x] delivery endpoint writes sanitized audit rows.
- [x] delivery audit list is tenant-scoped.
- [x] delivery responses do not expose webhook payloads, headers, or channel secrets.
- [x] frontend analytics helpers create/list channels, deliver alerts, and list audit logs.
- [x] dashboard renders delivery channels and recent delivery audit.

Scheduled alert evaluation and cooldown:

- [x] default alert evaluator worker settings are disabled.
- [x] alert evaluator worker settings can be enabled and configured.
- [x] alert evaluator worker lifecycle installer registers only when enabled.
- [x] alert evaluator worker `run_once` evaluates tenant policies.
- [x] cooldown suppresses repeated delivery for the same channel and alert code.
- [x] cooldown suppression does not write duplicate audit rows.
- [x] delivery resumes after the configured cooldown window.
- [x] scheduled evaluation report does not expose payloads, headers, or secrets.

Runbook export and incident handoff:

- [x] dispatch runbook endpoint requires authentication.
- [x] dispatch runbook returns tenant-scoped health, policy, alerts, deliveries, and recommended actions.
- [x] dispatch runbook quiet state returns a low-severity no-action handoff.
- [x] dispatch runbook markdown export is downloadable.
- [x] dispatch runbook responses and markdown do not expose payloads, headers, workflow definitions, encrypted config, or secrets.
- [x] frontend analytics helpers fetch and export dispatch runbooks.
- [x] dashboard renders dispatch runbook handoff without secrets.

Incident acknowledgement and ownership:

- [x] acknowledgement read requires authentication.
- [x] owner/editor can acknowledge the current active dispatch incident.
- [x] viewer cannot acknowledge dispatch incidents.
- [x] quiet dispatch runbook state cannot be acknowledged.
- [x] re-acknowledging the same incident updates ownership/note without duplicate open rows.
- [x] acknowledgement note is sanitized.
- [x] dispatch runbook includes current acknowledgement metadata.
- [x] acknowledgement is tenant-scoped.
- [x] frontend analytics helpers read/write acknowledgement.
- [x] dashboard shows incident owner and acknowledgement action without secrets.

Incident resolution history and review notes:

- [x] owner/editor can resolve the current acknowledged dispatch incident.
- [x] viewer cannot resolve dispatch incidents.
- [x] resolving without an open acknowledgement returns `409`.
- [x] resolved incident no longer appears as current runbook owner.
- [x] incident history is tenant-scoped.
- [x] resolution note is sanitized.
- [x] incident history does not expose payloads, headers, workflow definitions, encrypted config, or secrets.
- [x] frontend analytics helpers resolve incidents and fetch incident history.
- [x] dashboard shows resolve action and recent incident history without secrets.

Incident analytics trends and SLA reporting:

- [x] incident analytics endpoint returns tenant-scoped totals and SLA breach counts.
- [x] daily incident trend is zero-filled for the full requested window.
- [x] severity breakdown reports total, resolved, open, breach, and average resolution metrics.
- [x] open incidents older than `sla_minutes` count as SLA breaches.
- [x] analytics responses do not expose notes, user identity, payloads, headers, workflow definitions, encrypted config, or secrets.
- [x] analytics query parameters validate `days` and `sla_minutes`.
- [x] frontend analytics helper fetches incident analytics with window/SLA params.
- [x] dashboard renders incident analytics metrics, trend, and severity breakdown without secrets.

Dispatch control automation recommendations:

- [x] recommendation endpoint returns tenant-scoped automation candidates from health, policy, and SLA signals.
- [x] dead-lettered dispatches recommend approval-gated retry automation.
- [x] paused workflow dispatch recommends resume guard automation.
- [x] throttled webhook triggers recommend rate-limit tuning automation.
- [x] SLA breaches recommend escalation automation.
- [x] disabled alert routing recommends alert-routing setup.
- [x] recommendation endpoint is dry-run and does not mutate state.
- [x] recommendation responses do not expose notes, user identity, payloads, headers, workflow definitions, encrypted config, credential targets, or secrets.
- [x] query parameters validate `window_hours` and `sla_minutes`.
- [x] frontend analytics helper fetches dispatch control recommendations.
- [x] dashboard renders automation recommendations without secrets.

Approval-gated automation execution plans:

- [x] owner/editor can create a pending automation plan from a current recommendation.
- [x] unknown or stale recommendation code returns `409`.
- [x] duplicate pending plan for the same recommendation code returns `409`.
- [x] viewer cannot create automation plans.
- [x] owner can approve a pending plan.
- [x] viewer/editor cannot approve plans.
- [x] owner can reject a pending plan with sanitized note.
- [x] approved/rejected plans cannot be approved or rejected again.
- [x] plan list is tenant-scoped.
- [x] approving/rejecting plans does not mutate dispatch state or send notifications.
- [x] plan responses do not expose notes, payloads, headers, workflow definitions, encrypted config, credential targets, notification secrets, or raw automation payloads.

Approval-gated automation execution worker:

- [x] worker claims only approved automation plans.
- [x] approved `resume_guard` plan resumes paused tenant workflows only when dispatch health is safe.
- [x] unsafe `resume_guard` plan is blocked without resuming workflows.
- [x] unsupported automation types are blocked with sanitized execution result.
- [x] terminal plans are not picked up again.
- [x] worker reports claimed, executed, blocked, and failed counts.
- [x] worker execution results do not expose notes, payloads, headers, workflow definitions, encrypted config, credential targets, notification secrets, or raw automation payloads.
- [x] worker does not send external notifications.

Approval-gated dead-letter retry execution:

- [x] approved `approval_gated_retry` plan creates one pending retry execution for an eligible tenant dead-lettered webhook execution.
- [x] automated retry preserves manual retry lineage and records the automation plan id.
- [x] source dead-lettered execution remains failed and auditable.
- [x] retry plans without eligible dead-lettered executions are blocked with sanitized execution result.
- [x] worker does not retry another tenant's dead-lettered execution.
- [x] automated retry execution results do not expose payloads, headers, workflow definitions, encrypted config, credential targets, notification secrets, or raw automation payloads.
- [x] automated retry worker still uses existing execution creation validation, budget, and concurrency checks.

Automation plan controls and execution history UI:

- [x] frontend analytics helper lists dispatch automation plans.
- [x] frontend analytics helper creates, approves, and rejects dispatch automation plans through existing endpoints.
- [x] dashboard loads automation plans with dispatch recommendations.
- [x] owner/editor can create pending automation plans from current recommendations.
- [x] owner can approve or reject pending automation plans.
- [x] viewer can inspect automation plan history but cannot see create, approve, or reject actions.
- [x] automation plan history renders sanitized statuses/results without notes, operator identities, payloads, headers, workflow definitions, encrypted config, credential targets, notification secrets, or raw automation payloads.

Guarded automation worker run control:

- [x] owner can call `POST /api/v1/analytics/dispatch-automation-worker/run` and receive run_id plus claimed/executed/blocked/failed counts.
- [x] editor/viewer cannot call the manual worker run endpoint.
- [x] invalid worker run `limit` is rejected.
- [x] worker run response does not expose execution results, payloads, headers, workflow definitions, encrypted config, credential targets, notification secrets, rejection notes, operator identities, or raw automation payloads.
- [x] frontend analytics helper posts to the worker run endpoint with a limit.
- [x] dashboard renders a guarded owner-only run worker button.
- [x] dashboard refreshes automation plan history after a worker run.
- [x] editor/viewer dashboard does not render the worker run button.

Automation worker schedule config and run audit:

- [x] default worker schedule config is disabled with a 15 minute interval and 10 plan run limit.
- [x] owner can update worker schedule config.
- [x] editor/viewer cannot update worker schedule config.
- [x] invalid schedule interval and max plan limits are rejected.
- [x] manual worker runs write durable tenant-scoped audit rows.
- [x] audit row list is tenant-scoped and does not expose actor identity fields.
- [x] frontend analytics helpers read/update worker config and list run audit rows.
- [x] dashboard renders worker schedule state and recent worker runs.
- [x] dashboard renders owner-only schedule mutation controls.
- [x] dashboard does not render schedule mutation controls for viewers.

Config-gated automation scheduler loop:

- [x] scheduler settings default to globally disabled.
- [x] lifecycle installer leaves scheduler absent when globally disabled.
- [x] lifecycle installer registers scheduler when globally enabled.
- [x] scheduler loop starts and stops cleanly.
- [x] scheduler skips tenants whose worker config is disabled.
- [x] scheduler skips enabled tenants whose scheduled interval has not elapsed.
- [x] scheduler runs approved plans for enabled due tenants using tenant `max_plans_per_run`.
- [x] scheduler writes durable `trigger_type="scheduled"` audit rows.
- [x] scheduler-level failures write sanitized audit rows.
- [x] scheduler reports aggregate counts without secrets or raw automation payloads.

Automation scheduler leader lock:

- [x] scheduler skips without scanning tenants when the leader lock is unavailable.
- [x] scheduler does not execute plans or write audit rows when the leader lock is unavailable.
- [x] scheduler releases the leader lock after successful scheduled evaluation.
- [x] scheduler releases the leader lock after scheduler-level tenant failure.
- [x] PostgreSQL lock helper uses advisory lock/unlock statements.
- [x] non-PostgreSQL test/local lock helper falls back to acquired.
- [x] scheduler reports lock acquired/skipped state without secrets.

Tenant scheduler fairness and backoff:

- [x] disabled tenants do not consume due execution slots.
- [x] interval-skipped tenants do not consume due execution slots.
- [x] backoff-skipped tenants do not consume due execution slots.
- [x] scheduler continues scanning until due tenant limit is processed or candidates are exhausted.
- [x] failed scheduled audit rows apply tenant-level failure backoff.
- [x] due tenants behind skipped tenants still execute.
- [x] scheduler reports `tenants_skipped_backoff` separately from interval skips.

Scheduler observability and admin diagnostics:

- [x] owner can read scheduler diagnostics.
- [x] editor/viewer cannot read scheduler diagnostics.
- [x] diagnostics include global scheduler enabled flag, interval seconds, and tenant limit.
- [x] diagnostics include tenant worker config.
- [x] diagnostics include approved automation plan backlog count.
- [x] diagnostics include latest scheduled audit row without actor identity.
- [x] diagnostics include tenant due state, skip reason, next run time, and backoff until.
- [x] diagnostics are read-only and do not mutate plans, workflows, or audit rows.
- [x] diagnostics do not expose payloads, headers, workflow definitions, encrypted config, secrets, notes, or operator identity.

Dashboard scheduler diagnostics panel:

- [x] frontend analytics helper fetches scheduler diagnostics from the owner-only endpoint.
- [x] dashboard loads diagnostics for owners without blocking existing analytics data.
- [x] dashboard does not fail for non-owner roles when diagnostics are unavailable.
- [x] owner panel renders global scheduler state, interval seconds, tenant limit, tenant schedule config, approved backlog, and tenant readiness.
- [x] owner panel renders latest scheduled run audit with aggregate counts and sanitized error text.
- [x] viewer/editor roles do not render the diagnostics panel.
- [x] panel does not render payloads, headers, workflow definitions, encrypted config, secrets, notes, raw automation payloads, or operator identity.
- [x] panel is read-only and does not expose mutation controls.

Internal scheduler fleet operations snapshot:

- [x] internal service reports global scheduler metadata and aggregate tenant readiness counts.
- [x] internal service reports approved automation backlog across tenants without executing plans.
- [x] per-tenant readiness summaries include due, interval, backoff, and disabled states without names, slugs, identities, payloads, headers, workflow definitions, or secrets.
- [x] aggregate-only mode omits per-tenant summaries.
- [x] snapshot generation is read-only and does not mutate plans, workflows, audit rows, scheduler state, or external systems.
- [x] no public cross-tenant endpoint or dashboard is added before a platform-admin authorization model exists.

Platform-admin scheduler fleet API:

- [x] platform admin can read scheduler fleet diagnostics across tenants.
- [x] tenant owner/editor/viewer users cannot read cross-tenant scheduler fleet diagnostics.
- [x] fleet diagnostics response reports global scheduler metadata, readiness counts, approved backlog, and per-tenant readiness summaries.
- [x] `include_tenants=false` returns aggregate counts with an empty tenant summary list.
- [x] response does not expose tenant names, slugs, operator identities, emails, raw errors, payloads, headers, workflow definitions, encrypted config, credential targets, notification secrets, or raw automation payloads.
- [x] endpoint is read-only and does not mutate plans, workflows, audit rows, scheduler state, or external systems.
- [x] tenant owners cannot invite or assign platform-admin roles through tenant user management.

Platform-admin scheduler fleet dashboard:

- [x] frontend analytics helper fetches scheduler fleet diagnostics from the platform-admin endpoint.
- [x] dashboard loads scheduler fleet diagnostics only for `platform_admin` users.
- [x] platform-admin dashboard renders global scheduler state, fleet readiness counts, approved backlog, and tenant readiness summaries.
- [x] owner/editor/viewer dashboards do not fetch or render the fleet panel.
- [x] panel does not render tenant names, slugs, operator identities, emails, raw errors, payloads, headers, workflow definitions, encrypted config, credential targets, notification secrets, or raw automation payloads.
- [x] panel is read-only and does not expose worker run, schedule mutation, plan approval, or tenant management controls.

## Slice Boundaries

Slice 1:

- no frontend changes;
- no new database columns;
- no external queue;
- no mutation of source execution history.

Slice 2:

- no backend changes beyond Slice 1 contract;
- no new database columns;
- no external queue;
- no raw webhook payload/header rendering.

Slice 3:

- backend-only control surface;
- database columns are allowed for durable operator state;
- no frontend UI yet;
- no external queue;
- no raw webhook payload/header logging.

Slice 4:

- no new database columns;
- trigger-level limits live in webhook trigger config;
- rate limit is enforced before webhook event or execution creation;
- queue filters reuse existing execution list endpoint;
- no raw webhook payload/header rendering.

Slice 5:

- no new database columns;
- no persisted alert delivery yet;
- analytics endpoint only returns aggregate counts and alert summaries;
- dashboard displays operator health without workflow definitions, payloads, or headers.

Slice 6:

- small tenant JSONB column is allowed for policy persistence;
- no external notification delivery;
- no channel credentials or secrets;
- preview uses current dispatch health alerts and policy filters.

Slice 7:

- real external delivery adapters are implemented but tests must mock outbound HTTP;
- webhook channel credentials are encrypted at rest;
- audit logs store sanitized operational results only;
- cooldown scheduling is deferred to Slice 8.

Slice 8:

- no new frontend changes;
- no new external adapters;
- worker is config-gated and disabled by default;
- cooldown uses sanitized delivery audit rows and must not log secrets;
- tests must mock outbound HTTP.

Slice 19:

- schedule config storage is allowed in tenant JSONB;
- durable worker run audit table is allowed;
- manual runs record audit rows after the existing guarded worker finishes;
- no background scheduler loop is started in this slice;
- audit responses do not expose actor identities or raw automation payloads.

Slice 20:

- add only an in-process scheduler loop, not distributed locks;
- global scheduler setting remains disabled by default;
- tenant worker config remains the second gate;
- interval enforcement uses the latest scheduled audit row;
- scheduled run audit rows contain aggregate counts only;
- frontend changes are not required because Slice 19 already added schedule controls and audit UI.

Slice 21:

- add scheduler-level leader locking only;
- do not add distributed queues or tenant-level leases;
- do not change dashboard UI;
- PostgreSQL uses advisory locks; SQLite tests use acquired fallback;
- unavailable lock means no tenant scan, no plan execution, and no audit writes.

Slice 22:

- no new frontend UI;
- no new database table;
- failure backoff is derived from scheduled audit history;
- due tenant limit no longer means first raw tenant rows only;
- skipped tenants do not consume due execution capacity.

Slice 23:

- backend/API diagnostics only;
- no dashboard UI changes;
- no new database columns;
- no scheduler execution from diagnostics;
- global scheduler enabled state is diagnostic metadata only.

Slice 24:

- frontend dashboard/read-only UI only;
- no backend behavior changes;
- no schedule mutation controls in the diagnostics panel;
- owner-only diagnostics are hidden from viewer/editor dashboards.

Slice 25:

- backend/internal service only;
- no public cross-tenant API or dashboard;
- no new database table or column;
- no scheduler execution, plan claiming, or audit writes;
- fleet summaries must omit tenant names, slugs, identities, raw errors, payloads, headers, workflow definitions, encrypted config, credential targets, notification secrets, and raw automation payloads.

Slice 26:

- backend API/auth only;
- no frontend dashboard UI yet;
- no new database table or column;
- platform-admin authorization must be explicit, not tenant-owner based;
- endpoint must reuse the Slice 25 read-only snapshot and remain sanitized.

Slice 27:

- frontend dashboard/read-only UI only;
- no backend behavior changes;
- no worker run, schedule mutation, plan approval, or tenant management controls in the fleet panel;
- fleet diagnostics are loaded only for `platform_admin` users;
- tenant-local dashboards remain unaffected when fleet diagnostics are unavailable.

Slice 9:

- no new database tables;
- no external notification delivery;
- runbook export is read-only;
- export surfaces sanitized operator context only.

Slice 10:

- one small persistence table is allowed for incident ownership;
- no external notifications;
- no raw payloads, headers, workflow definitions, or encrypted config in acknowledgement APIs/UI;
- acknowledgement derives incident identity from current sanitized runbook alerts.

Slice 11:

- no new external notifications;
- one additive migration is allowed for resolution metadata;
- history is read-only and tenant-scoped;
- review notes must be sanitized.

## Required Verification

```bash
cd backend
python -m pytest tests/test_execution_dispatch_controls.py -q
python -m pytest tests/test_workflow_dispatch_controls.py -q
python -m pytest tests/test_connector_runtime.py -q
python -m pytest tests/test_analytics.py -q
python -m pytest tests/test_dispatch_alert_policy.py -q
python -m pytest tests/test_dispatch_alert_delivery.py -q
python -m pytest tests/test_dispatch_alert_evaluator_worker.py -q
python -m pytest tests/test_dispatch_runbook.py -q
python -m pytest tests/test_dispatch_incident_acknowledgement.py -q
python -m pytest tests/test_dispatch_incident_resolution.py -q
python -m pytest tests/test_webhook_dispatcher.py tests/test_webhook_dispatcher_worker.py tests/test_connector_runtime.py -q
python -m ruff check app tests alembic
python -m pytest -q
cd ../frontend
npm test -- analytics.test.js DispatchAlertPolicyPanel.test.jsx DispatchHealthPanel.test.jsx
npm test -- analytics.test.js DispatchAlertDeliveryPanel.test.jsx DispatchAlertPolicyPanel.test.jsx
npm test -- analytics.test.js DispatchRunbookPanel.test.jsx
npm test -- analytics.test.js DispatchRunbookPanel.test.jsx
npm test -- analytics.test.js DispatchHealthPanel.test.jsx
npm test -- executions.test.js DispatchQueuePanel.test.jsx ConnectorWorkspacePanel.test.jsx
npm test
npm run build
npm audit --audit-level=high
```

Current environment note: `npm audit --audit-level=high` requires an outbound
request to the public npm service and was blocked by policy during Slice 7
verification. Run it only with explicit approval for that external check.
