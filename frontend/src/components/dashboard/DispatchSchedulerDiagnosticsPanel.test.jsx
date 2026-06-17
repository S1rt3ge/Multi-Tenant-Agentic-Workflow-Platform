import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import DispatchSchedulerDiagnosticsPanel from './DispatchSchedulerDiagnosticsPanel';

describe('DispatchSchedulerDiagnosticsPanel', () => {
  const diagnostics = {
    generated_at: '2026-05-25T10:30:00Z',
    scheduler_enabled: false,
    scheduler_interval_seconds: 60,
    scheduler_tenant_limit: 25,
    tenant_config: {
      enabled: true,
      interval_minutes: 15,
      max_plans_per_run: 10,
    },
    approved_plan_count: 3,
    latest_scheduled_run: {
      id: 'run-1',
      trigger_type: 'scheduled',
      status: 'failed',
      limit: 10,
      claimed: 2,
      executed: 1,
      blocked: 0,
      failed: 1,
      error_message: 'Authorization: **** ****',
      created_at: '2026-05-25T10:00:00Z',
      triggered_by_email: 'owner@test.com',
      payload: 'secret-webhook-payload',
      headers: { authorization: 'Bearer secret-diagnostics-token' },
    },
    tenant_due_now: false,
    tenant_skip_reason: 'backoff',
    next_run_at: '2026-05-25T10:45:00Z',
    backoff_until: '2026-05-25T11:00:00Z',
    workflow_definition: { nodes: ['secret-node'] },
  };

  it('renders owner scheduler readiness, backlog, and sanitized latest audit', () => {
    const html = renderToStaticMarkup(
      <DispatchSchedulerDiagnosticsPanel
        diagnostics={diagnostics}
        userRole="owner"
      />
    );

    expect(html).toContain('Scheduler diagnostics');
    expect(html).toContain('Global scheduler');
    expect(html).toContain('disabled');
    expect(html).toContain('Every 60s');
    expect(html).toContain('Tenant limit 25');
    expect(html).toContain('Tenant schedule');
    expect(html).toContain('Every 15 min');
    expect(html).toContain('Max 10 plans');
    expect(html).toContain('Approved backlog');
    expect(html).toContain('3');
    expect(html).toContain('Backoff');
    expect(html).toContain('Latest scheduled run');
    expect(html).toContain('scheduled');
    expect(html).toContain('failed');
    expect(html).toContain('claimed: 2');
    expect(html).toContain('executed: 1');
    expect(html).toContain('Authorization: **** ****');
    expect(html).not.toContain('owner@test.com');
    expect(html).not.toContain('secret-webhook-payload');
    expect(html).not.toContain('secret-diagnostics-token');
    expect(html).not.toContain('workflow_definition');
  });

  it('renders ready state without mutation controls', () => {
    const html = renderToStaticMarkup(
      <DispatchSchedulerDiagnosticsPanel
        diagnostics={{
          ...diagnostics,
          scheduler_enabled: true,
          tenant_due_now: true,
          tenant_skip_reason: null,
          next_run_at: null,
          backoff_until: null,
          latest_scheduled_run: null,
        }}
        userRole="owner"
      />
    );

    expect(html).toContain('enabled');
    expect(html).toContain('Ready now');
    expect(html).toContain('No scheduled worker runs recorded yet');
    expect(html).not.toContain('Run worker');
    expect(html).not.toContain('Enable schedule');
    expect(html).not.toContain('Disable schedule');
  });

  it('renders nothing for non-owner roles or missing diagnostics', () => {
    expect(renderToStaticMarkup(
      <DispatchSchedulerDiagnosticsPanel diagnostics={diagnostics} userRole="viewer" />
    )).toBe('');
    expect(renderToStaticMarkup(
      <DispatchSchedulerDiagnosticsPanel diagnostics={diagnostics} userRole="editor" />
    )).toBe('');
    expect(renderToStaticMarkup(
      <DispatchSchedulerDiagnosticsPanel diagnostics={null} userRole="owner" />
    )).toBe('');
  });
});
