# M8 Idea: Workflow Doctor

## 1. Problem

Graph-based automation platforms make it easy to build workflows, but failed runs are still mostly debugged by hand.

Current user flow in most workflow tools:

1. A run fails.
2. The user opens execution logs.
3. The user guesses whether the issue is a bad tool config, bad auth, invalid data shape, model output, timeout, or workflow graph issue.
4. The user edits a node manually.
5. The user retries the workflow.
6. The workflow may fail again at the same or next step.

Concrete pain:

- A simple API tool failure can take 10-30 minutes to diagnose when the user has to inspect logs, tool config, headers, and input payloads manually.
- A broken multi-agent workflow can take 30-90 minutes to repair because prompt behavior, graph routing, and tool outputs interact.
- Users avoid complex automations because each failure creates operational risk.

The product opportunity is to turn GraphPilot from a workflow runner into a workflow repair system.

## 2. Solution

Workflow Doctor diagnoses failed executions, proposes safe fixes, previews patches, and replays the affected workflow path before the user applies the change.

Core flow:

1. User opens a failed execution.
2. User clicks `Diagnose`.
3. Backend analyzes execution, logs, workflow definition, agent configs, and tool configs.
4. System returns a root-cause report with confidence and a suggested patch.
5. User opens patch preview.
6. User runs sandbox replay.
7. User applies the patch and retries the workflow.

MVP behavior is rule-based and deterministic. LLM-assisted diagnosis is a later enhancement.

## 3. Why Now

AI workflow builders are becoming more complex than traditional automation tools because they include:

- non-deterministic LLM steps;
- tool calls with auth and network constraints;
- graph routing based on model output;
- token budgets and model/provider limits;
- multi-tenant security boundaries.

Traditional retry buttons are not enough for this class of workflows. The next product step is self-healing execution infrastructure.

## 4. Target Audience

Primary audience:

- builders of internal AI workflows;
- automation engineers replacing brittle Zapier/n8n scripts;
- AI ops teams maintaining multi-agent processes;
- founders and engineers building workflow-heavy SaaS operations.

Secondary audience:

- agencies building automations for clients;
- support teams that need reliable handoffs between tools;
- data teams that need auditable run repair.

## 5. Differentiation

GraphPilot should not compete only on having a visual canvas. It should compete on operational intelligence.

Positioning:

> n8n helps you automate workflows. GraphPilot helps workflows debug themselves.

Competitive gap:

- Existing automation tools expose execution logs and retry controls.
- GraphPilot adds structured root-cause diagnosis, safe patch suggestions, and replay before applying a fix.

## 6. MVP Scope

MVP includes:

- failed execution diagnosis;
- rule-based detectors;
- persisted fix suggestions;
- patch preview;
- safe apply for a narrow set of patch types;
- sandbox replay that validates graph/config without external side effects;
- UI panel on the execution page.

MVP excludes:

- fully autonomous patch application;
- writing secrets;
- external API replay with side effects;
- LLM-generated code patches;
- parallel branch replay;
- production queue migration.

## 7. v2 Scope

v2 adds:

- LLM-assisted diagnosis summaries;
- node input/output contracts;
- schema mismatch detection between connected nodes;
- suggested data mappers;
- partial replay from failed node;
- tool-specific fix packs for common SaaS APIs;
- benchmark dashboard for mean time to repair.

## 8. Architecture

New backend components:

- `WorkflowFixSuggestion` model;
- diagnosis service;
- patch validation service;
- replay service;
- API routes under executions and fix suggestions.

Existing components reused:

- `Execution`;
- `ExecutionLog`;
- `Workflow`;
- `AgentConfig`;
- `ToolRegistry`;
- tenant and role dependencies;
- analytics cache invalidation after retry.

New frontend components:

- `WorkflowDoctorPanel`;
- `FixSuggestionCard`;
- `PatchPreview`;
- `ReplayStatus`;
- `ApplyAndRetryButton`.

## 9. Monetization

Free plan:

- view diagnosis for the latest failed execution;
- no auto-apply;
- no historical diagnosis archive.

Pro plan:

- unlimited diagnosis;
- apply and retry;
- replay validation;
- node contracts.

Team plan:

- team-wide repair history;
- approval workflow;
- advanced audit log;
- AI-assisted diagnosis.

## 10. Risks

| Risk | Probability | Impact | Mitigation |
| --- | --- | --- | --- |
| Suggested patch makes workflow worse | Medium | High | Require preview, confidence score, and manual approval |
| Secrets leak through diagnosis | Medium | High | Mask configs before diagnosis output; never include raw secret values |
| Replay causes external side effects | Low in MVP | High | MVP replay is validation-only and does not call external APIs or LLMs |
| Diagnosis is too generic | Medium | Medium | Start with deterministic rule detectors tied to known error classes |
| Tenant data leaks across diagnosis | Low | High | Every query scoped by `tenant_id`; tests for cross-tenant isolation |
| Patch application bypasses RBAC | Low | High | Apply requires `owner` or `editor`; viewers can only read suggestions |

## 11. Success Metrics

MVP success:

- `POST /executions/{id}/diagnose` returns a useful diagnosis for at least 8 common failure classes.
- 90% of diagnosis responses complete in under 2 seconds for executions with fewer than 100 logs.
- Patch preview never includes raw secrets.
- Apply and retry works for supported patch types.

Product success:

- Reduce mean time to repair a failed workflow from 10-30 minutes to under 3 minutes.
- Increase successful retry rate after first diagnosis.
- Make the demo obviously different from generic workflow automation.

## 12. Demo Script

Demo failure:

1. Create workflow with one API tool using an unreachable HTTPS host.
2. Start or test the workflow.
3. Execution/tool validation fails.
4. Click `Diagnose`.
5. Doctor reports `api_url_resolution_failed`.
6. Doctor proposes replacing URL with a resolvable HTTPS endpoint.
7. User previews patch.
8. User applies patch.
9. User retries.

Demo message:

> This is not just observability. This is repair.
