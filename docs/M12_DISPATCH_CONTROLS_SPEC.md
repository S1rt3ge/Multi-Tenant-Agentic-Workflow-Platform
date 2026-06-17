# M12 Spec: Operator-Grade Dispatch Controls

Date: 2026-05-17
Status: slice 27 green

## Goals

1. Add safe operator controls on top of the M11 durable webhook dispatch pipeline.
2. Preserve execution history: controls create new execution rows instead of rewriting completed/failed runs.
3. Keep controls tenant-scoped and editor/owner-gated.
4. Keep webhook payloads and headers out of operator UI additions.

## Slice 1 Contract: Manual Dead-Letter Retry

Endpoint:

- `POST /api/v1/executions/{execution_id}/retry`

Authorization:

- requires authenticated `owner` or `editor`;
- `viewer` receives `403`;
- execution lookup remains tenant-scoped.

Eligible source execution:

- `status == "failed"`;
- `input_data.trigger.type == "webhook"`;
- `input_data.dispatch.dead_lettered == true`.

Behavior:

- keep the source execution unchanged;
- create a new `pending` execution for the same workflow and tenant;
- copy source `input_data`;
- preserve webhook trigger data;
- update `input_data.dispatch` on the new execution:
  - increment `attempt`;
  - preserve or establish `root_execution_id`;
  - set `parent_execution_id` to the source execution ID;
  - set `previous_execution_id` to the source execution ID;
  - set `manual_retry = true`;
  - set `requested_by_user_id` to the acting user ID;
  - clear `dead_lettered`, `dead_letter_reason`, and `next_attempt_at`.

Response:

- status `201`;
- response body contains:
  - `execution_id`;
  - `status`;
  - `source_execution_id`.

## Slice 2 Contract: Connector Workspace Retry Action

Location:

- Builder connector workspace.
- `DispatchQueuePanel`.

Behavior:

- render a `Retry` action only for dead-letter webhook executions;
- hide retry action for viewers;
- call `POST /api/v1/executions/{execution_id}/retry`;
- show an in-flight state for the execution being retried;
- refresh connector workspace dispatch queue after successful retry;
- do not render webhook payloads or headers.

Frontend API helper:

- `retryExecution(executionId)`.

Expected response:

- `{ execution_id, source_execution_id, status }`.

## Slice 3 Contract: Workflow Dispatch Pause/Resume

Endpoints:

- `POST /api/v1/workflows/{workflow_id}/dispatch/pause`
- `POST /api/v1/workflows/{workflow_id}/dispatch/resume`

Authorization:

- requires authenticated `owner` or `editor`;
- `viewer` receives `403`;
- workflow lookup remains tenant-scoped.

Persistent workflow state:

- `dispatch_paused: bool`, default `false`;
- `dispatch_paused_at: datetime | null`;
- `dispatch_paused_by: UUID | null`.

Behavior:

- pause sets `dispatch_paused = true` and records actor/time;
- resume sets `dispatch_paused = false` and clears pause metadata;
- webhook dispatcher skips pending webhook executions whose workflow is paused;
- skipped paused executions remain `pending`;
- manual execution start remains governed by existing workflow execution rules and is not changed in Slice 3.

Response:

- status `200`;
- body contains workflow dispatch control state.

## Slice 4 Contract: Trigger Rate Limits and Queue Filtering

Webhook trigger config:

- rate limits are configured per trigger in `WorkflowTrigger.config.rate_limit`;
- supported shape:
  - `enabled: bool`;
  - `max_events: int`;
  - `window_seconds: int`;
- disabled or missing rate limit config preserves existing behavior.

Webhook ingest behavior:

- enforce the rate limit before creating a `WebhookEvent` or `Execution`;
- count accepted webhook events for the same tenant and trigger in the configured rolling window;
- when the limit is exceeded, return `429 Too Many Requests`;
- response detail must not include webhook payloads or headers;
- rate-limited requests must not create pending executions.

Dispatch queue filtering:

- connector workspace can filter webhook dispatch executions by operational state;
- filters are local UI controls backed by existing tenant-scoped execution listing;
- frontend API helper may pass `status_filter` through to the existing executions endpoint;
- filter labels must not collide with the dead-letter `Retry` action label;
- filtered queue must still hide non-webhook executions and raw webhook payload/header data.

## Slice 5 Contract: Dispatch Health Metrics and Alerts

Endpoint:

- `GET /api/v1/analytics/dispatch-health`

Authorization:

- requires authenticated user;
- response is tenant-scoped;
- viewers may read aggregated health metrics.

Query:

- `window_hours`, default `24`, min `1`, max `720`;
- window applies to execution-derived counts;
- paused workflow and rate-limit exhaustion are current-state checks.

Response:

- `paused_workflows`;
- `throttled_triggers`;
- `pending_dispatches`;
- `deferred_retries`;
- `dead_lettered_executions`;
- `manual_retries`;
- `alerts[]` with `code`, `severity`, `title`, `message`, and `count`.

Behavior:

- count only webhook-triggered dispatch executions for execution-derived metrics;
- count paused active workflows for `paused_workflows`;
- count active webhook triggers whose configured rate-limit window is currently exhausted for `throttled_triggers`;
- do not persist throttled request attempts, because Slice 4 intentionally rejects over-limit requests before event/execution creation;
- generate alerts when paused workflows, throttled triggers, deferred retries, or dead-letter executions are present;
- alerts must contain only aggregate counts and operational text.

## Slice 6 Contract: Alert Routing Policy and Dry-Run Preview

Endpoints:

- `GET /api/v1/analytics/dispatch-alert-policy`
- `PUT /api/v1/analytics/dispatch-alert-policy`
- `POST /api/v1/analytics/dispatch-alert-policy/preview`

Authorization:

- policy read requires authenticated user;
- policy update requires `owner` or `editor`;
- preview requires authenticated user;
- all policy data is tenant-scoped.

Persistent state:

- `tenants.dispatch_alert_policy: JSONB`, default `{}`;
- service normalizes empty policy to safe defaults.

Policy shape:

- `enabled: bool`;
- `channels[]` with `type`, `target`, and `enabled`;
- `severities[]`, allowed `critical`, `warning`, `info`;
- `alert_codes[]`, allowed `dispatch_paused`, `trigger_throttled`, `deferred_retries`, `dead_lettered`;
- `cooldown_minutes`, bounded to avoid notification storms.

Preview behavior:

- dry-run only, no external messages are sent;
- uses current `dispatch-health` alerts;
- filters alerts through stored policy severity and code rules;
- returns matched alerts and planned routes;
- disabled policy may return matched alerts but no planned routes;
- response must not include workflow definitions, webhook payloads, webhook headers, secrets, or execution input data.

## Slice 7 Contract: Notification Delivery Adapters and Audit Logs

Endpoints:

- `POST /api/v1/analytics/dispatch-alert-channels`
- `GET /api/v1/analytics/dispatch-alert-channels`
- `POST /api/v1/analytics/dispatch-alert-deliveries`
- `GET /api/v1/analytics/dispatch-alert-deliveries`

Authorization:

- channel create requires `owner` or `editor`;
- delivery trigger requires `owner` or `editor`;
- channel list and delivery audit list require authenticated user;
- all channel credentials and delivery logs are tenant-scoped.

Persistent state:

- `dispatch_alert_channel_credentials`;
- `dispatch_alert_deliveries`.

Channel credential behavior:

- Slice 7 supports `webhook` delivery credentials;
- webhook `url` and optional `headers` are encrypted at rest;
- API responses expose only non-secret previews;
- private or restricted network webhook URLs are rejected;
- policy channels can reference `credential_id` for real delivery.

Delivery behavior:

- delivery sends only alert summaries generated by `dispatch-health`;
- delivery respects policy `enabled`, severity filters, alert code filters, channel enabled flags, and credential references;
- delivery writes one audit row per alert/channel result;
- delivery audit stores status, sanitized error, status code, channel type, and non-secret target preview;
- delivery endpoint is the only place real external notification attempts happen.

Supported adapters:

- `webhook` via outbound HTTP POST.

## Slice 8 Contract: Scheduled Alert Evaluation and Cooldown

Runtime:

- `DispatchAlertEvaluationWorker` is disabled by default and enabled only by config;
- worker evaluates tenant dispatch alert policies on a fixed interval;
- worker uses the same sanitized delivery path as manual dispatch alert delivery;
- worker tests must mock outbound notification delivery.

Cooldown behavior:

- policy `cooldown_minutes` suppresses repeat delivery per `tenant_id + channel_id + alert_code`;
- cooldown is based on recent `dispatch_alert_deliveries.created_at` rows;
- suppressed alerts increment `skipped` and do not create extra delivery audit rows;
- cooldown applies to scheduled and manual delivery calls.

Report behavior:

- worker reports scanned tenant count, evaluated tenant count, attempted, delivered, failed, skipped, and evaluated tenant ids;
- report data must not contain workflow definitions, webhook payloads, webhook headers, encrypted config, or notification secrets.

## Slice 9 Contract: Runbook Export and Incident Handoff

Endpoints:

- `GET /api/v1/analytics/dispatch-runbook`

Authorization:

- requires authenticated user;
- runbook data is tenant-scoped.

Runbook behavior:

- returns an operator-facing dispatch incident snapshot;
- includes generated timestamp, window, health metrics, matched alerts, policy status, configured channel count, recent sanitized delivery audit rows, and recommended actions;
- supports `format=json` and `format=markdown`;
- markdown export uses `text/markdown` and attachment filename `dispatch_runbook.md`;
- quiet state returns a low-severity summary and a no-action recommendation.

Security behavior:

- runbook must not include workflow definitions, execution input data, webhook payloads, webhook headers, encrypted config, or notification secrets;
- runbook export does not send external notifications;
- runbook export does not mutate delivery audit or policy state.

## Slice 10 Contract: Incident Acknowledgement and Ownership

Endpoints:

- `GET /api/v1/analytics/dispatch-incident-acknowledgement`
- `POST /api/v1/analytics/dispatch-incident-acknowledgement`

Authorization:

- acknowledgement read requires authenticated user;
- acknowledgement write requires `owner` or `editor`;
- `viewer` receives `403` on write;
- all acknowledgement rows are tenant-scoped.

Persistent state:

- `dispatch_incident_acknowledgements`.

Acknowledgement behavior:

- acknowledgement applies only to the current active dispatch incident from the runbook;
- current incident identity is derived from sorted active alert codes;
- acknowledging assigns current incident ownership to the current operator;
- re-acknowledging the same active incident updates ownership and note instead of creating duplicate open rows;
- quiet runbook state cannot be acknowledged and returns `409`;
- runbook response includes current acknowledgement metadata when present.

Security behavior:

- acknowledgement notes are sanitized;
- acknowledgement responses must not expose webhook payloads, webhook headers, workflow definitions, encrypted configs, or notification secrets;
- acknowledgement does not send external notifications.

## Slice 11 Contract: Incident Resolution History and Review Notes

Endpoints:

- `POST /api/v1/analytics/dispatch-incident-acknowledgement/resolve`
- `GET /api/v1/analytics/dispatch-incident-history`

Authorization:

- incident history read requires authenticated user;
- incident resolve requires `owner` or `editor`;
- `viewer` receives `403` on resolve;
- all resolution history rows are tenant-scoped.

Resolution behavior:

- resolving requires an open acknowledgement for the current active dispatch incident;
- resolving marks the acknowledgement row as `resolved`;
- resolver metadata and sanitized resolution note are persisted;
- resolved acknowledgement no longer appears as the current runbook owner;
- incident history lists recent acknowledged and resolved incidents for post-incident review.

Security behavior:

- resolution notes are sanitized;
- history responses must not expose webhook payloads, webhook headers, workflow definitions, encrypted configs, or notification secrets;
- resolving does not send external notifications.

## Slice 12 Contract: Incident Analytics Trends and SLA Reporting

Endpoint:

- `GET /api/v1/analytics/dispatch-incident-analytics`

Query parameters:

- `days`: trend window, `1..365`, default `30`;
- `sla_minutes`: acknowledgement-to-resolution SLA threshold, `1..10080`, default `60`.

Authorization:

- incident analytics read requires authenticated user;
- all metrics are tenant-scoped;
- viewers may read analytics but cannot mutate incident state.

Analytics behavior:

- totals count tenant incident acknowledgement rows created inside the trend window;
- resolved count includes rows with `status = resolved` and `resolved_at`;
- open count includes acknowledged rows without a resolution timestamp;
- SLA breach count includes resolved rows whose resolution duration is greater than `sla_minutes` and open rows whose current age is greater than `sla_minutes`;
- average resolution minutes is computed only from resolved rows;
- daily trends are zero-filled for the full requested window;
- severity breakdown groups incidents by severity with total, resolved, open, SLA breach, and average resolution metrics.

Security behavior:

- analytics responses expose only aggregate counts, severities, dates, and durations;
- responses must not expose acknowledgement notes, resolution notes, webhook payloads, webhook headers, workflow definitions, encrypted configs, notification secrets, user emails, or user names;
- analytics read must not send external notifications or mutate incident rows.

## Slice 13 Contract: Dispatch Control Automation Recommendations

Endpoint:

- `GET /api/v1/analytics/dispatch-control-recommendations`

Query parameters:

- `window_hours`: dispatch health window, `1..720`, default `24`;
- `sla_minutes`: incident SLA threshold, `1..10080`, default `60`.

Authorization:

- recommendation read requires authenticated user;
- all recommendation evidence is tenant-scoped;
- viewers may read recommendations but cannot trigger dispatch mutations through this endpoint.

Recommendation behavior:

- recommendations are generated from dispatch health, alert policy, and incident SLA analytics;
- dead-lettered dispatches produce an approval-gated retry automation recommendation;
- paused workflow dispatch produces a resume-guard automation recommendation;
- exhausted webhook trigger rate limits produce a rate-limit tuning recommendation;
- SLA breaches produce an escalation automation recommendation;
- disabled alert routing produces an alert-routing setup recommendation;
- the endpoint is dry-run only and must not retry, resume, change rate limits, update policy, deliver notifications, or mutate incidents.

Security behavior:

- responses expose only aggregate evidence and non-secret recommendation metadata;
- responses must not expose acknowledgement notes, resolution notes, user identities, webhook payloads, webhook headers, workflow definitions, encrypted configs, notification secrets, or credential targets;
- recommendation reads must not send external notifications.

## Slice 14 Contract: Approval-Gated Automation Execution Plans

Endpoints:

- `POST /api/v1/analytics/dispatch-automation-plans`
- `GET /api/v1/analytics/dispatch-automation-plans`
- `POST /api/v1/analytics/dispatch-automation-plans/{plan_id}/approve`
- `POST /api/v1/analytics/dispatch-automation-plans/{plan_id}/reject`

Authorization:

- plan list requires authenticated user;
- plan creation requires `owner` or `editor`;
- approval/rejection requires `owner`;
- viewers cannot create, approve, or reject plans;
- all plan rows are tenant-scoped.

Plan behavior:

- plan creation materializes one current dispatch control recommendation into a persistent approval record;
- unknown or stale recommendation codes return `409`;
- duplicate pending plans for the same recommendation code return `409`;
- approval marks a pending plan as `approved` and stores approver metadata;
- rejection marks a pending plan as `rejected` and stores sanitized rejection note plus rejector metadata;
- approved/rejected plans cannot be approved or rejected again;
- plan approval remains dry-run and must not retry executions, resume workflows, update rate limits, update alert policy, deliver notifications, or mutate incidents.

Security behavior:

- plan responses expose only sanitized recommendation metadata, aggregate evidence, and non-secret operator metadata;
- responses must not expose acknowledgement notes, resolution notes, webhook payloads, webhook headers, workflow definitions, encrypted configs, credential targets, notification secrets, or raw automation payloads;
- plan creation, approval, and rejection must not send external notifications.

## Slice 15 Contract: Approval-Gated Automation Execution Worker

Service:

- `dispatch_automation_plan_worker.run_dispatch_automation_plan_worker_once`

Execution behavior:

- worker only claims plans with `status = approved`;
- claimed plans move to `executing`;
- supported safe automation types are executed locally and write sanitized `execution_result`;
- unsupported automation types are marked `blocked` with a sanitized reason;
- failed execution is marked `failed` with a sanitized reason;
- executed/blocked/failed plans are terminal and are not picked up again;
- worker reports aggregate counts for claimed, executed, blocked, and failed plans.

Supported safe actions:

- `resume_guard`: when the tenant has paused workflows and current dispatch health has no dead-lettered executions, no deferred retries, and no throttled triggers, resume tenant paused workflow dispatch;
- all other automation types remain blocked until their execution contracts are specified in later slices.

Security behavior:

- worker never sends external notifications;
- worker never exposes webhook payloads, webhook headers, workflow definitions, encrypted configs, credential targets, notification secrets, acknowledgement notes, resolution notes, or raw automation payloads in execution results;
- worker is tenant-scoped and cannot mutate other tenants' workflows;
- worker is idempotent for terminal plans.

## Slice 16 Contract: Approval-Gated Dead-Letter Retry Execution

Service:

- `dispatch_automation_plan_worker.run_dispatch_automation_plan_worker_once`

Execution behavior:

- worker supports approved plans with `automation_type = approval_gated_retry`;
- each approved retry plan creates at most one new pending retry execution for the oldest eligible tenant source execution;
- eligible source execution follows the Slice 1 retry contract:
  - `status == "failed"`;
  - `input_data.trigger.type == "webhook"`;
  - `input_data.dispatch.dead_lettered == true`;
- source executions that already have a manual or automated child retry are skipped;
- retry execution preserves the manual retry lineage metadata and additionally records the automation plan id;
- source execution remains failed and dead-lettered for audit history;
- plans without an eligible source are marked `blocked` with a sanitized reason;
- successful plans are marked `executed` with sanitized aggregate result fields only.

Security behavior:

- worker never retries executions from another tenant;
- worker never exposes webhook payloads, webhook headers, workflow definitions, encrypted configs, credential targets, notification secrets, acknowledgement notes, resolution notes, or raw automation payloads in execution results;
- worker does not send external notifications;
- worker still uses the existing execution creation path so workflow validation, budget checks, and concurrency limits remain enforced.

## Slice 17 Contract: Automation Plan Controls and Execution History UI

Frontend surfaces:

- dashboard automation recommendations panel;
- `analytics.js` automation plan API helpers;
- `useDashboard` automation plan state/actions.

Operator behavior:

- dashboard loads tenant automation plans alongside dispatch recommendations;
- owner/editor users can materialize a current recommendation into a pending approval plan;
- owners can approve or reject pending approval plans from the dashboard;
- viewers can inspect plan history but cannot see create, approve, or reject actions;
- successful create/approve/reject actions refresh local plan history and do not execute automation directly;
- plan history displays plan status, automation type, recommendation code, priority, timestamps, and sanitized execution result summaries.

Security behavior:

- UI must not render webhook payloads, webhook headers, workflow definitions, encrypted configs, credential targets, notification secrets, rejection notes, or raw automation payloads;
- UI should avoid rendering operator emails/names in the dashboard history;
- frontend actions rely on existing backend role and tenant enforcement.

## Slice 18 Contract: Guarded Automation Worker Run Control

Endpoint:

- `POST /api/v1/analytics/dispatch-automation-worker/run`

Query parameters:

- `limit`: max approved plans to claim in one run, `1..50`, default `10`.

Authorization:

- endpoint requires authenticated `owner`;
- editors and viewers receive `403`;
- worker execution remains tenant-scoped through approved plan rows.

Execution behavior:

- endpoint runs `dispatch_automation_plan_worker.run_dispatch_automation_plan_worker_once` once;
- response returns only aggregate counts: `claimed`, `executed`, `blocked`, `failed`;
- endpoint does not create, approve, or reject automation plans;
- approving a plan remains dry-run until this guarded run endpoint is called;
- dashboard exposes a guarded owner-only run button and refreshes plan history after a run.

Security behavior:

- response must not include execution results, payloads, headers, workflow definitions, encrypted configs, credential targets, notification secrets, rejection notes, operator identities, or raw automation payloads;
- endpoint must not send external notifications;
- frontend must not render the run control for editors or viewers.

## Slice 19 Contract: Automation Worker Schedule Config And Run Audit

Endpoints:

- `GET /api/v1/analytics/dispatch-automation-worker/config`
- `PUT /api/v1/analytics/dispatch-automation-worker/config`
- `GET /api/v1/analytics/dispatch-automation-worker/runs`
- `POST /api/v1/analytics/dispatch-automation-worker/run`

Schedule config:

- stored per tenant in `tenants.dispatch_automation_worker_config`;
- default is disabled: `enabled=false`, `interval_minutes=15`, `max_plans_per_run=10`;
- interval is validated as `5..1440` minutes;
- max plans per run is validated as `1..50`;
- authenticated users can read the current config;
- only owners can update the config.

Run audit:

- manual worker runs write durable rows to `dispatch_automation_worker_runs`;
- each audit row stores tenant, trigger type, status, limit, aggregate counts, optional sanitized error, and timestamp;
- manual run response includes `run_id` plus aggregate counts only;
- run audit list is tenant-scoped and sorted newest first;
- run audit responses do not expose actor identity fields.

Dashboard behavior:

- dashboard loads worker schedule config and recent worker runs with automation recommendations;
- owners can enable or disable the schedule config from the dashboard;
- viewers can inspect schedule state and run history but cannot mutate config or run the worker;
- worker run history renders only trigger type, status, timestamp, aggregate counts, and sanitized error text.

Security behavior:

- schedule config updates are owner-only;
- run audit responses must not include payloads, headers, workflow definitions, encrypted configs, credential targets, notification secrets, rejection notes, operator identities, or raw automation payloads;
- storing schedule config does not start a background scheduler in this slice;
- no external notifications are sent by config reads/updates or run audit reads.

## Slice 20 Contract: Config-Gated Automation Scheduler Loop

Runtime:

- add an in-process dispatch automation worker scheduler;
- scheduler installation is controlled by global environment settings and remains disabled by default;
- when globally enabled, the scheduler scans tenants up to a configured tenant limit;
- tenant execution remains gated by `tenants.dispatch_automation_worker_config.enabled`;
- scheduler uses each tenant's `interval_minutes` to skip tenants whose latest scheduled audit row is still inside the interval window;
- scheduler runs approved automation plans with the tenant's `max_plans_per_run`;
- scheduler writes durable audit rows with `trigger_type="scheduled"`.

Settings:

- `DISPATCH_AUTOMATION_WORKER_ENABLED`, default `false`;
- `DISPATCH_AUTOMATION_WORKER_INTERVAL_SECONDS`, default `60.0`;
- `DISPATCH_AUTOMATION_WORKER_TENANT_LIMIT`, default `25`.

Report behavior:

- scheduler reports tenants scanned, enabled, due, skipped by interval, failed tenants, and aggregate claimed/executed/blocked/failed counts;
- scheduler reports must not include payloads, headers, workflow definitions, encrypted configs, credential targets, notification secrets, operator identities, or raw automation payloads.

Security behavior:

- scheduler must not run for disabled tenant configs;
- scheduler must not run before tenant interval has elapsed;
- scheduler must not claim plans across tenants;
- scheduler-level failures write sanitized audit rows and do not stop evaluation of other tenants;
- scheduler does not send external notifications.

## Slice 21 Contract: Automation Scheduler Leader Lock

Runtime:

- scheduled automation evaluation must acquire a scheduler-level leader lock before scanning tenants;
- when the lock is not acquired, the scheduler returns a skipped report and does not scan tenants, execute plans, or write audit rows;
- when the lock is acquired, it is released after successful evaluation;
- when tenant execution fails, the lock is still released after sanitized failure audit is written;
- PostgreSQL deployments use advisory locks for cross-process safety;
- non-PostgreSQL local/test deployments use an acquired fallback lock so existing SQLite tests remain deterministic.

Report behavior:

- scheduler reports whether the leader lock was acquired or skipped;
- lock reports must not expose database connection details, payloads, headers, workflow definitions, encrypted configs, credential targets, notification secrets, operator identities, or raw automation payloads.

Security behavior:

- lock acquisition failure must be fail-closed for scheduled execution;
- lock release failures may be logged but must not expose secrets;
- leader lock is scheduler-level, not tenant-level, for this slice.

## Slice 22 Contract: Tenant Scheduler Fairness And Backoff

Runtime:

- scheduler `limit` applies to due tenant executions, not to the first raw tenant rows scanned;
- disabled tenants, interval-skipped tenants, and backoff-skipped tenants do not consume due execution slots;
- scheduler continues scanning until it has processed the due tenant limit or exhausted tenant candidates;
- failed scheduled audit rows apply a tenant-level failure backoff before the next scheduled attempt;
- failure backoff defaults to 30 minutes and is never shorter than the tenant `interval_minutes`;
- due tenants behind disabled/not-due/backoff tenants still receive a scheduled execution slot.

Report behavior:

- scheduler reports backoff-skipped tenants separately from interval-skipped tenants;
- scheduler reports scanned tenants and due tenants distinctly;
- reports must not expose payloads, headers, workflow definitions, encrypted configs, credential targets, notification secrets, operator identities, or raw automation payloads.

Security behavior:

- backoff must be tenant-scoped;
- one tenant's disabled config, interval state, or failure backoff must not block another tenant's due scheduled automation;
- no frontend changes are required in this slice.

## Slice 23 Contract: Scheduler Observability And Admin Diagnostics

Endpoint:

- `GET /api/v1/analytics/dispatch-automation-worker/diagnostics`

Authorization:

- endpoint requires authenticated `owner`;
- editors and viewers receive `403`.

Diagnostic behavior:

- response is tenant-scoped;
- response includes global scheduler settings needed for operator debugging: enabled flag, interval seconds, and tenant scan limit;
- response includes tenant worker config;
- response includes approved automation plan backlog count;
- response includes latest scheduled run audit row, if present;
- response includes tenant-level due state: `tenant_due_now`, `tenant_skip_reason`, `next_run_at`, and `backoff_until`;
- global scheduler disabled state is reported separately and does not hide tenant due diagnostics.

Security behavior:

- diagnostics must not expose payloads, headers, workflow definitions, encrypted configs, credential targets, notification secrets, rejection notes, operator identities, or raw automation payloads;
- diagnostics must not mutate plans, workflow dispatch state, audit rows, or external systems.

## Slice 24 Contract: Dashboard Scheduler Diagnostics Panel

Location:

- Dashboard.
- New scheduler diagnostics panel rendered near automation recommendations.

Data source:

- dashboard uses `GET /api/v1/analytics/dispatch-automation-worker/diagnostics`.

Dashboard behavior:

- owners can inspect global scheduler enabled state, scheduler interval seconds, and scheduler tenant limit;
- owners can inspect tenant worker schedule config, approved automation backlog, tenant due state, skip reason, next run time, and backoff time;
- owners can inspect the latest scheduled audit row with trigger type, status, timestamp, aggregate counts, and sanitized error text;
- viewers and editors do not render the diagnostics panel;
- dashboard loading must not fail for non-owner roles because diagnostics are owner-only.

Security behavior:

- panel must not render payloads, headers, workflow definitions, encrypted configs, credential targets, notification secrets, rejection notes, operator identities, or raw automation payloads;
- panel is read-only and must not expose schedule mutation controls or worker execution controls.

## Slice 25 Contract: Internal Scheduler Fleet Operations Snapshot

Service:

- `dispatch_automation_worker_scheduler.inspect_dispatch_automation_scheduler_fleet`

Runtime behavior:

- provide a read-only, internal scheduler fleet snapshot for operator-grade diagnostics and future platform-admin tooling;
- summarize all tenant worker configs without executing the scheduler or claiming automation plans;
- report global scheduler metadata: enabled flag, scheduler interval seconds, and scheduler tenant limit;
- report aggregate tenant readiness counts: total tenants, configured tenants, enabled tenants, disabled tenants, due tenants, interval-waiting tenants, and backoff tenants;
- report aggregate approved automation plan backlog across tenants;
- optionally include per-tenant readiness summaries for internal diagnostics;
- per-tenant summaries include only tenant id, enabled flag, due state, skip reason, approved plan count, latest scheduled status/time, next run time, backoff time, and max plans per run.

Security behavior:

- the snapshot is an internal service contract only in this slice; do not expose a public cross-tenant API or dashboard until a platform-admin authorization model exists;
- snapshot generation must not mutate plans, workflows, audit rows, scheduler state, or external systems;
- snapshot data must not include tenant names, slugs, operator identities, emails, notes, payloads, headers, workflow definitions, encrypted configs, credential targets, notification secrets, scheduler error messages, or raw automation payloads;
- aggregate-only mode must be available so future call sites can avoid per-tenant identifiers when they only need fleet counts.

## Slice 26 Contract: Platform-Admin Scheduler Fleet API

Endpoint:

- `GET /api/v1/analytics/dispatch-automation-worker/fleet`

Authorization:

- endpoint requires authenticated `platform_admin`;
- tenant `owner`, `editor`, and `viewer` users receive `403`;
- tenant owners cannot invite or assign `platform_admin` through tenant user management.

Query:

- `include_tenants`, default `true`;
- when `include_tenants=false`, response returns aggregate counts only and an empty tenant summary list.

Behavior:

- endpoint wraps the Slice 25 internal fleet snapshot;
- response reports global scheduler metadata, fleet readiness counts, approved automation plan backlog, and optional per-tenant readiness summaries;
- endpoint is read-only and must not run the scheduler, claim plans, write audit rows, mutate workflow dispatch state, or contact external systems;
- tenant summaries expose tenant IDs only plus schedule readiness fields; tenant names and slugs are not returned.

Security behavior:

- response must not expose tenant names, slugs, operator identities, emails, notes, payloads, headers, workflow definitions, encrypted configs, credential targets, notification secrets, scheduler error messages, or raw automation payloads;
- the platform-admin guard is explicit and must not be replaceable by tenant-local `owner` authorization.

## Slice 27 Contract: Platform-Admin Scheduler Fleet Dashboard

Location:

- Dashboard.
- New read-only scheduler fleet panel rendered near existing scheduler diagnostics.

Data source:

- dashboard uses `GET /api/v1/analytics/dispatch-automation-worker/fleet`;
- dashboard loads the fleet endpoint only when `user.role == "platform_admin"`.

Dashboard behavior:

- platform admins can inspect global scheduler state, scheduler interval seconds, tenant limit, total tenants, enabled/disabled tenant counts, due/interval/backoff counts, and approved backlog;
- platform admins can inspect sanitized tenant readiness summaries by tenant id only;
- tenant owner/editor/viewer dashboards do not fetch or render the fleet panel;
- panel is read-only and does not expose worker run, schedule mutation, plan approval, or tenant management controls.

Security behavior:

- panel must not render tenant names, slugs, operator identities, emails, notes, payloads, headers, workflow definitions, encrypted configs, credential targets, notification secrets, scheduler error messages, or raw automation payloads;
- a missing or forbidden fleet response must not break existing tenant dashboards.

## Security Rules

- Do not expose retry as a public webhook endpoint.
- Do not allow cross-tenant retries.
- Do not allow viewers to retry executions.
- Do not mutate source execution status/logs.
- Do not log webhook payloads or headers.
- Do not bypass existing workflow validation, budget, or concurrency checks when creating the retry execution.
- Do not store or render raw webhook headers/payloads in new rate-limit or queue-filter UI.
- Do not create execution rows for rate-limited webhook requests.
- Do not expose workflow definitions, webhook payloads, webhook headers, or execution input data in dispatch health responses.
- Do not send real emails, webhooks, Slack messages, or any external notifications in Slice 6.
- Do not store channel credentials or secrets in dispatch alert policy.
- Do not expose encrypted notification configs or raw secrets in channel, delivery, preview, logs, or UI responses.
- Do not deliver alerts to policy channels that lack a credential reference.
- Do not call private or loopback notification URLs.
- Do not create repeated delivery attempts inside the configured alert cooldown.
- Do not write cooldown-suppressed audit rows on every scheduler tick.
- Do not include raw workflow definitions, payloads, headers, encrypted configs, or notification secrets in runbook exports.
- Do not mutate state while generating a runbook handoff.
- Do not allow viewers to acknowledge or take ownership of incidents.
- Do not create acknowledgement rows when no active dispatch incident exists.
- Do not allow incident resolution without an open acknowledgement.
- Do not expose secrets in incident history or resolution notes.
- Do not expose notes, user identity, payloads, headers, workflow definitions, encrypted configs, or notification secrets in incident analytics.
- Do not mutate dispatch state, alert policy, incidents, or external systems while generating automation recommendations.
- Do not expose notes, user identity, payloads, headers, workflow definitions, encrypted configs, credential targets, or notification secrets in automation recommendations.
- Do not execute automation, retry dispatches, resume workflows, change rate limits, update policies, mutate incidents, or send notifications when approving an automation plan.
- Do not expose notes, payloads, headers, workflow definitions, encrypted configs, credential targets, notification secrets, or raw automation payloads in automation plan responses.
- Do not execute unsupported automation types.
- Do not resume workflow dispatch unless the approved resume guard plan is tenant-scoped and current dispatch health is safe.
- Do not expose notes, payloads, headers, workflow definitions, encrypted configs, credential targets, notification secrets, or raw automation payloads in automation execution results.
- Do not create automated retry executions for source executions that already have a retry child.
- Do not render automation plan rejection notes, operator identities, payloads, headers, workflow definitions, encrypted configs, credential targets, notification secrets, or raw automation payloads in dashboard automation history.
- Do not expose raw plan execution results or operator identity fields in manual worker run responses.
- Do not let editors or viewers trigger the manual automation worker run endpoint.
- Do not let editors or viewers update automation worker schedule config.
- Do not expose actor identity, notes, payloads, headers, workflow definitions, encrypted configs, credential targets, notification secrets, or raw automation payloads in automation worker run audit responses.
- Do not start a background automation scheduler from Slice 19 config storage alone.
- Do not run scheduled automation for tenants whose worker config is disabled.
- Do not run scheduled automation again before the tenant interval has elapsed.
- Do not let one tenant's scheduled automation failure stop other tenant evaluations.
- Do not scan tenants, execute plans, or write scheduled audit rows when the scheduler leader lock is not acquired.
- Do not hold the scheduler leader lock after successful or failed evaluation.
- Do not let disabled, interval-skipped, or backoff-skipped tenants consume due execution slots.
- Do not let one tenant's failure backoff block another due tenant.
- Do not expose operator identity, payloads, headers, workflow definitions, encrypted configs, credential targets, notification secrets, rejection notes, or raw automation payloads in scheduler diagnostics.
- Do not mutate scheduler state while generating diagnostics.
- Do not expose a cross-tenant scheduler fleet endpoint or UI until a platform-admin authorization model exists.
- Do not expose tenant names, slugs, identities, scheduler errors, payloads, headers, workflow definitions, encrypted configs, credential targets, notification secrets, or raw automation payloads in internal scheduler fleet snapshots.
- Do not mutate scheduler, workflow, plan, audit, or external state while generating scheduler fleet snapshots.
- Do not allow tenant owners, editors, or viewers to read cross-tenant scheduler fleet diagnostics.
- Do not allow tenant user management to invite or assign platform-admin roles.
- Do not expose tenant names, slugs, identities, scheduler errors, payloads, headers, workflow definitions, encrypted configs, credential targets, notification secrets, or raw automation payloads in platform-admin fleet API responses.
- Do not fetch or render platform-admin fleet diagnostics for tenant-local owner, editor, or viewer dashboards.
- Do not expose tenant names, slugs, identities, scheduler errors, payloads, headers, workflow definitions, encrypted configs, credential targets, notification secrets, or raw automation payloads in platform-admin fleet dashboard panels.

## Acceptance Criteria

- Dead-letter webhook execution can be retried by an editor/owner.
- Retry creates a new pending execution.
- Retry execution has incremented attempt and lineage metadata.
- Source execution remains failed and dead-lettered.
- Non-dead-letter executions return `409`.
- Viewer retry attempt returns `403`.
- Other tenant cannot retry the execution.
- Existing M11 dispatcher tests remain green.
- Connector workspace renders retry action for dead-letter executions.
- Connector workspace does not render retry action for viewers.
- Retry action calls backend helper and refreshes dispatch queue.
- Dispatch queue UI still does not render webhook payloads or headers.
- Workflow dispatch can be paused and resumed by an owner/editor.
- Viewer cannot pause or resume workflow dispatch.
- Cross-tenant users cannot pause or resume workflow dispatch.
- Dispatcher skips pending webhook executions for paused workflows.
- Existing M11/M12 regression tests remain green.
- Webhook trigger rate limit returns `429` when exceeded.
- Rate-limited webhook request does not create a new execution.
- Missing or disabled trigger rate limit preserves existing webhook ingest behavior.
- Dispatch queue API helper can pass `status_filter`.
- Dispatch queue UI can filter all, active, deferred, dead-letter, and completed states.
- Dispatch queue filtering still excludes non-webhook executions and raw webhook data.
- Dispatch health endpoint returns tenant-scoped aggregate metrics.
- Dispatch health endpoint reports paused workflows.
- Dispatch health endpoint reports triggers whose rate-limit windows are exhausted.
- Dispatch health endpoint reports dead-letter, deferred retry, pending dispatch, and manual retry counts.
- Dispatch health alerts contain no webhook payloads or headers.
- Dashboard renders dispatch health metrics and alerts.
- Dashboard handles empty dispatch health without noisy alerts.
- Dispatch alert policy has a safe default.
- Owner/editor can update dispatch alert policy.
- Viewer cannot update dispatch alert policy.
- Dispatch alert policy preview returns dry-run routes for matching alerts.
- Dispatch alert policy preview sends no external notifications.
- Dashboard renders alert routing policy and dry-run preview.
- Dispatch alert channel credentials are encrypted at rest.
- Dispatch alert channel API responses expose only previews.
- Delivery endpoint posts webhook alerts for matched credential-backed policy channels.
- Delivery endpoint writes sanitized audit rows.
- Delivery audit list is tenant-scoped.
- Dashboard renders configured delivery channels and recent delivery audit.
- Alert delivery respects policy cooldown per channel and alert code.
- Scheduled alert evaluation worker is disabled by default and config-gated.
- Scheduled worker reuses the sanitized delivery path and reports aggregate outcomes.
- Dispatch runbook endpoint returns a tenant-scoped incident handoff snapshot.
- Dispatch runbook markdown export is sanitized and downloadable.
- Dashboard renders the dispatch runbook handoff and can trigger markdown export.
- Owner/editor can acknowledge the current dispatch incident.
- Viewer cannot acknowledge dispatch incidents.
- Runbook shows current incident owner without exposing secrets.
- Owner/editor can resolve the current acknowledged incident with a sanitized review note.
- Viewer cannot resolve incidents.
- Incident history lists tenant-scoped acknowledgement/resolution rows.
- Incident analytics reports tenant-scoped totals, trends, severity breakdowns, and SLA breaches.
- Incident analytics zero-fills daily trend windows.
- Incident analytics responses expose no notes, user identity, payloads, headers, workflow definitions, encrypted configs, or secrets.
- Dispatch control recommendations are tenant-scoped and generated from health, policy, and incident SLA signals.
- Dispatch control recommendations remain dry-run and mutate no dispatch state.
- Dispatch control recommendations expose no notes, user identity, payloads, headers, workflow definitions, encrypted configs, credential targets, or secrets.
- Dispatch automation plans can be created only from current tenant recommendations.
- Duplicate pending automation plans for the same recommendation are rejected.
- Automation plan approval/rejection is tenant-scoped, role-gated, and remains dry-run.
- Dispatch automation worker claims only approved plans.
- Dispatch automation worker safely resumes paused workflow dispatch only through approved resume guard plans.
- Dispatch automation worker blocks unsupported automation types with sanitized results.
- Dispatch automation worker does not re-run terminal plans.
- Approved dead-letter retry automation plans create one pending retry execution through the existing manual retry path.
- Automated retry plans skip dead-letter sources that already have a retry child.
- Automated retry execution results expose only aggregate counts and execution IDs.
- Dashboard can create automation plans from current recommendations for owner/editor users.
- Dashboard can approve or reject pending automation plans for owners.
- Dashboard renders automation plan history without exposing notes, operator identities, payloads, headers, workflow definitions, encrypted configs, credential targets, notification secrets, or raw automation payloads.
- Owner can manually run the dispatch automation worker once from the dashboard.
- Manual worker run response contains only aggregate counts.
- Automation worker schedule config is tenant-scoped, disabled by default, owner-gated for updates, and validated.
- Manual automation worker runs create durable tenant-scoped audit rows.
- Worker run audit responses contain only run id, trigger type, status, limit, aggregate counts, sanitized error, and timestamp.
- Dashboard renders schedule config and recent worker run audit without exposing operator identities or secrets.
- Viewer dashboard does not render schedule mutation controls.
- Automation scheduler is globally disabled by default.
- Automation scheduler runs enabled tenant configs only when their interval is due.
- Automation scheduler writes scheduled run audit rows.
- Automation scheduler-level failures are sanitized in audit rows.
- Automation scheduler skips without mutation when the leader lock is unavailable.
- Automation scheduler releases the leader lock after success and after tenant-level failures.
- Automation scheduler applies tenant-level failure backoff after failed scheduled audit rows.
- Automation scheduler protects due tenants from starvation behind disabled/not-due/backoff tenants.
- Owner can inspect tenant-scoped scheduler diagnostics.
- Scheduler diagnostics report config, backlog, latest scheduled audit, and tenant due/backoff state without secrets.
- Owner dashboard renders scheduler diagnostics without exposing secrets or operator identities.
- Viewer/editor dashboards do not render owner-only scheduler diagnostics.
- Internal scheduler fleet snapshot reports global scheduler metadata and aggregate tenant readiness counts.
- Internal scheduler fleet snapshot reports approved automation backlog without executing plans.
- Internal scheduler fleet snapshot can omit per-tenant summaries for aggregate-only diagnostics.
- Internal scheduler fleet snapshot is read-only and sanitized.
- Platform admin can read scheduler fleet diagnostics across tenants.
- Tenant-local owner/editor/viewer users cannot read scheduler fleet diagnostics.
- Fleet diagnostics API can omit per-tenant summaries with `include_tenants=false`.
- Fleet diagnostics API is read-only and sanitized.
- Platform-admin dashboard loads and renders scheduler fleet diagnostics.
- Tenant owner/editor/viewer dashboards do not load or render scheduler fleet diagnostics.
- Scheduler fleet dashboard panel is read-only and sanitized.

## Future Slices

- Slice 28: platform-admin fleet filtering, search, and tenant drilldown with explicit audit logging.
