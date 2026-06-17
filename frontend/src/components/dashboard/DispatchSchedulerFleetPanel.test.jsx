import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import DispatchSchedulerFleetPanel from './DispatchSchedulerFleetPanel';

describe('DispatchSchedulerFleetPanel', () => {
  const fleet = {
    generated_at: '2026-05-28T20:00:00Z',
    scheduler_enabled: false,
    scheduler_interval_seconds: 60,
    scheduler_tenant_limit: 25,
    total_tenants: 4,
    configured_tenants: 3,
    enabled_tenants: 2,
    disabled_tenants: 2,
    due_tenants: 1,
    interval_waiting_tenants: 1,
    backoff_tenants: 1,
    approved_plan_backlog: 7,
    tenants: [
      {
        tenant_id: 'tenant-due',
        enabled: true,
        due_now: true,
        skip_reason: null,
        approved_plan_count: 3,
        latest_scheduled_status: null,
        max_plans_per_run: 10,
        tenant_name: 'Hidden Tenant Name',
        slug: 'hidden-tenant-slug',
        owner_email: 'owner@test.com',
        workflow_definition: { nodes: ['secret-node'] },
      },
      {
        tenant_id: 'tenant-backoff',
        enabled: true,
        due_now: false,
        skip_reason: 'backoff',
        approved_plan_count: 4,
        latest_scheduled_status: 'failed',
        next_run_at: '2026-05-28T20:30:00Z',
        backoff_until: '2026-05-28T20:30:00Z',
        max_plans_per_run: 4,
        error_message: 'Authorization: Bearer secret-fleet-token',
      },
    ],
  };

  it('renders platform-admin fleet readiness and sanitized tenant summaries', () => {
    const html = renderToStaticMarkup(
      <DispatchSchedulerFleetPanel fleet={fleet} userRole="platform_admin" />
    );

    expect(html).toContain('Scheduler fleet');
    expect(html).toContain('platform-admin');
    expect(html).toContain('read-only');
    expect(html).toContain('Total tenants');
    expect(html).toContain('4');
    expect(html).toContain('Enabled');
    expect(html).toContain('Due now');
    expect(html).toContain('Backoff');
    expect(html).toContain('Approved backlog');
    expect(html).toContain('tenant-due');
    expect(html).toContain('tenant-backoff');
    expect(html).toContain('Max 10 plans');
    expect(html).toContain('Latest failed');
    expect(html).not.toContain('Hidden Tenant Name');
    expect(html).not.toContain('hidden-tenant-slug');
    expect(html).not.toContain('owner@test.com');
    expect(html).not.toContain('secret-node');
    expect(html).not.toContain('secret-fleet-token');
    expect(html).not.toContain('Authorization');
    expect(html).not.toContain('error_message');
  });

  it('renders aggregate-only fleet diagnostics without tenant rows', () => {
    const html = renderToStaticMarkup(
      <DispatchSchedulerFleetPanel
        fleet={{ ...fleet, tenants: [] }}
        userRole="platform_admin"
      />
    );

    expect(html).toContain('No tenant readiness rows in this snapshot');
    expect(html).toContain('Approved backlog');
    expect(html).not.toContain('tenant-due');
  });

  it('renders nothing for tenant-local roles or missing diagnostics', () => {
    expect(renderToStaticMarkup(
      <DispatchSchedulerFleetPanel fleet={fleet} userRole="owner" />
    )).toBe('');
    expect(renderToStaticMarkup(
      <DispatchSchedulerFleetPanel fleet={fleet} userRole="editor" />
    )).toBe('');
    expect(renderToStaticMarkup(
      <DispatchSchedulerFleetPanel fleet={fleet} userRole="viewer" />
    )).toBe('');
    expect(renderToStaticMarkup(
      <DispatchSchedulerFleetPanel fleet={null} userRole="platform_admin" />
    )).toBe('');
  });

  it('does not render mutation controls', () => {
    const html = renderToStaticMarkup(
      <DispatchSchedulerFleetPanel fleet={fleet} userRole="platform_admin" />
    );

    expect(html).not.toContain('Run worker');
    expect(html).not.toContain('Enable schedule');
    expect(html).not.toContain('Disable schedule');
    expect(html).not.toContain('Approve plan');
    expect(html).not.toContain('Reject plan');
    expect(html).not.toContain('Invite');
  });
});
