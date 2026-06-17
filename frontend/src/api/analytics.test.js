import { beforeEach, describe, expect, it, vi } from 'vitest';

import client from './client';
import {
  acknowledgeDispatchIncident,
  approveDispatchAutomationPlan,
  createDispatchAlertChannel,
  createDispatchAutomationPlan,
  deliverDispatchAlerts,
  exportDispatchRunbook,
  fetchDispatchAutomationWorkerFleetDiagnostics,
  fetchDispatchAutomationWorkerDiagnostics,
  fetchDispatchAutomationWorkerConfig,
  fetchDispatchAutomationPlans,
  fetchDispatchAutomationWorkerRuns,
  fetchDispatchIncidentHistory,
  fetchDispatchIncidentAcknowledgement,
  fetchDispatchIncidentAnalytics,
  fetchDispatchControlRecommendations,
  fetchDispatchAlertPolicy,
  fetchDispatchAlertChannels,
  fetchDispatchAlertDeliveries,
  fetchDispatchHealth,
  fetchDispatchRunbook,
  previewDispatchAlertPolicy,
  rejectDispatchAutomationPlan,
  resolveDispatchIncident,
  runDispatchAutomationWorker,
  updateDispatchAlertPolicy,
  updateDispatchAutomationWorkerConfig,
} from './analytics';

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
  },
}));

describe('analytics API helpers', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('fetches dispatch health with the default window', async () => {
    client.get.mockResolvedValueOnce({
      data: {
        paused_workflows: 1,
        throttled_triggers: 1,
        pending_dispatches: 3,
        deferred_retries: 1,
        dead_lettered_executions: 1,
        manual_retries: 1,
        alerts: [],
      },
    });

    await expect(fetchDispatchHealth()).resolves.toEqual({
      paused_workflows: 1,
      throttled_triggers: 1,
      pending_dispatches: 3,
      deferred_retries: 1,
      dead_lettered_executions: 1,
      manual_retries: 1,
      alerts: [],
    });

    expect(client.get).toHaveBeenCalledWith('/api/v1/analytics/dispatch-health', {
      params: { window_hours: 24 },
    });
  });

  it('fetches dispatch health with a custom window', async () => {
    client.get.mockResolvedValueOnce({
      data: {
        paused_workflows: 0,
        throttled_triggers: 0,
        pending_dispatches: 0,
        deferred_retries: 0,
        dead_lettered_executions: 0,
        manual_retries: 0,
        alerts: [],
      },
    });

    await fetchDispatchHealth(72);

    expect(client.get).toHaveBeenCalledWith('/api/v1/analytics/dispatch-health', {
      params: { window_hours: 72 },
    });
  });

  it('fetches dispatch alert policy', async () => {
    client.get.mockResolvedValueOnce({
      data: { enabled: false, channels: [], severities: ['critical'], alert_codes: [], cooldown_minutes: 30 },
    });

    await expect(fetchDispatchAlertPolicy()).resolves.toEqual({
      enabled: false,
      channels: [],
      severities: ['critical'],
      alert_codes: [],
      cooldown_minutes: 30,
    });

    expect(client.get).toHaveBeenCalledWith('/api/v1/analytics/dispatch-alert-policy');
  });

  it('updates dispatch alert policy', async () => {
    const policy = {
      enabled: true,
      channels: [{ type: 'email', target: 'ops@example.com', enabled: true }],
      severities: ['critical', 'warning'],
      alert_codes: ['dead_lettered'],
      cooldown_minutes: 15,
    };
    client.put = vi.fn().mockResolvedValueOnce({ data: policy });

    await expect(updateDispatchAlertPolicy(policy)).resolves.toEqual(policy);

    expect(client.put).toHaveBeenCalledWith('/api/v1/analytics/dispatch-alert-policy', policy);
  });

  it('previews dispatch alert policy routing without sending notifications', async () => {
    client.post = vi.fn().mockResolvedValueOnce({
      data: {
        dry_run: true,
        policy_enabled: true,
        alerts: [{ code: 'dead_lettered' }],
        routes: [{ channel_type: 'email', target: 'ops@example.com', alert_codes: ['dead_lettered'] }],
      },
    });

    await expect(previewDispatchAlertPolicy()).resolves.toEqual({
      dry_run: true,
      policy_enabled: true,
      alerts: [{ code: 'dead_lettered' }],
      routes: [{ channel_type: 'email', target: 'ops@example.com', alert_codes: ['dead_lettered'] }],
    });

    expect(client.post).toHaveBeenCalledWith('/api/v1/analytics/dispatch-alert-policy/preview');
  });

  it('creates and lists dispatch alert channels', async () => {
    const channel = {
      id: 'channel-1',
      name: 'Ops webhook',
      channel_type: 'webhook',
      config_preview: { url: 'https://hooks.example.com/dispatch' },
    };
    client.post = vi.fn().mockResolvedValueOnce({ data: channel });
    client.get.mockResolvedValueOnce({ data: { items: [channel] } });

    await expect(createDispatchAlertChannel({
      name: 'Ops webhook',
      channel_type: 'webhook',
      config: { url: 'https://hooks.example.com/dispatch' },
    })).resolves.toEqual(channel);
    await expect(fetchDispatchAlertChannels()).resolves.toEqual({ items: [channel] });

    expect(client.post).toHaveBeenCalledWith('/api/v1/analytics/dispatch-alert-channels', {
      name: 'Ops webhook',
      channel_type: 'webhook',
      config: { url: 'https://hooks.example.com/dispatch' },
    });
    expect(client.get).toHaveBeenCalledWith('/api/v1/analytics/dispatch-alert-channels');
  });

  it('delivers dispatch alerts and lists delivery audit rows', async () => {
    const delivery = {
      attempted: 1,
      delivered: 1,
      failed: 0,
      items: [{ id: 'delivery-1', status: 'delivered', alert_code: 'dead_lettered' }],
    };
    client.post = vi.fn().mockResolvedValueOnce({ data: delivery });
    client.get.mockResolvedValueOnce({ data: { items: delivery.items } });

    await expect(deliverDispatchAlerts()).resolves.toEqual(delivery);
    await expect(fetchDispatchAlertDeliveries()).resolves.toEqual({ items: delivery.items });

    expect(client.post).toHaveBeenCalledWith('/api/v1/analytics/dispatch-alert-deliveries');
    expect(client.get).toHaveBeenCalledWith('/api/v1/analytics/dispatch-alert-deliveries');
  });

  it('fetches and exports dispatch runbooks', async () => {
    const runbook = {
      severity: 'critical',
      summary: 'Dispatch incident handoff required',
      recommended_actions: [{ title: 'Review dead-letter queue' }],
    };
    client.get
      .mockResolvedValueOnce({ data: runbook })
      .mockResolvedValueOnce({ data: '# Dispatch Incident Runbook' });

    await expect(fetchDispatchRunbook()).resolves.toEqual(runbook);
    await expect(exportDispatchRunbook()).resolves.toBe('# Dispatch Incident Runbook');

    expect(client.get).toHaveBeenNthCalledWith(1, '/api/v1/analytics/dispatch-runbook', {
      params: { window_hours: 24, format: 'json' },
    });
    expect(client.get).toHaveBeenNthCalledWith(2, '/api/v1/analytics/dispatch-runbook', {
      params: { window_hours: 24, format: 'markdown' },
      responseType: 'blob',
    });
  });

  it('reads and writes dispatch incident acknowledgement', async () => {
    const acknowledgement = {
      id: 'ack-1',
      status: 'acknowledged',
      acknowledged_by_email: 'owner@test.com',
      note: 'Taking ownership',
    };
    client.get.mockResolvedValueOnce({ data: { acknowledgement } });
    client.post = vi.fn().mockResolvedValueOnce({ data: acknowledgement });

    await expect(fetchDispatchIncidentAcknowledgement()).resolves.toEqual({ acknowledgement });
    await expect(acknowledgeDispatchIncident('Taking ownership')).resolves.toEqual(acknowledgement);

    expect(client.get).toHaveBeenCalledWith('/api/v1/analytics/dispatch-incident-acknowledgement');
    expect(client.post).toHaveBeenCalledWith(
      '/api/v1/analytics/dispatch-incident-acknowledgement',
      { note: 'Taking ownership' }
    );
  });

  it('resolves incidents and fetches incident history', async () => {
    const resolved = {
      id: 'ack-1',
      status: 'resolved',
      resolved_by_email: 'owner@test.com',
      resolution_note: 'Fixed downstream issue',
    };
    client.post = vi.fn().mockResolvedValueOnce({ data: resolved });
    client.get.mockResolvedValueOnce({ data: { items: [resolved] } });

    await expect(resolveDispatchIncident('Fixed downstream issue')).resolves.toEqual(resolved);
    await expect(fetchDispatchIncidentHistory()).resolves.toEqual({ items: [resolved] });

    expect(client.post).toHaveBeenCalledWith(
      '/api/v1/analytics/dispatch-incident-acknowledgement/resolve',
      { resolution_note: 'Fixed downstream issue' }
    );
    expect(client.get).toHaveBeenCalledWith('/api/v1/analytics/dispatch-incident-history');
  });

  it('fetches dispatch incident analytics with trend and SLA params', async () => {
    const analytics = {
      window_days: 14,
      sla_minutes: 120,
      total_incidents: 3,
      resolved_incidents: 2,
      open_incidents: 1,
      sla_breaches: 1,
      trends: [],
      by_severity: [],
    };
    client.get.mockResolvedValueOnce({ data: analytics });

    await expect(fetchDispatchIncidentAnalytics(14, 120)).resolves.toEqual(analytics);

    expect(client.get).toHaveBeenCalledWith(
      '/api/v1/analytics/dispatch-incident-analytics',
      { params: { days: 14, sla_minutes: 120 } }
    );
  });

  it('fetches dispatch control automation recommendations', async () => {
    const recommendations = {
      dry_run: true,
      recommendation_count: 1,
      automation_ready_count: 1,
      recommendations: [{ code: 'auto_retry_dead_letters', priority: 'critical' }],
    };
    client.get.mockResolvedValueOnce({ data: recommendations });

    await expect(fetchDispatchControlRecommendations(72, 90)).resolves.toEqual(recommendations);

    expect(client.get).toHaveBeenCalledWith(
      '/api/v1/analytics/dispatch-control-recommendations',
      { params: { window_hours: 72, sla_minutes: 90 } }
    );
  });

  it('lists dispatch automation plans for dashboard history', async () => {
    const plans = {
      items: [
        {
          id: 'plan-1',
          recommendation_code: 'auto_retry_dead_letters',
          automation_type: 'approval_gated_retry',
          status: 'executed',
          execution_result: { retried_executions: 1 },
        },
      ],
    };
    client.get.mockResolvedValueOnce({ data: plans });

    await expect(fetchDispatchAutomationPlans()).resolves.toEqual(plans);

    expect(client.get).toHaveBeenCalledWith('/api/v1/analytics/dispatch-automation-plans', {
      params: { limit: 20 },
    });
  });

  it('creates approves and rejects dispatch automation plans', async () => {
    const pending = { id: 'plan-1', status: 'pending_approval' };
    const approved = { id: 'plan-1', status: 'approved' };
    const rejected = { id: 'plan-2', status: 'rejected' };
    client.post = vi.fn()
      .mockResolvedValueOnce({ data: pending })
      .mockResolvedValueOnce({ data: approved })
      .mockResolvedValueOnce({ data: rejected });

    await expect(createDispatchAutomationPlan('auto_retry_dead_letters')).resolves.toEqual(pending);
    await expect(approveDispatchAutomationPlan('plan-1')).resolves.toEqual(approved);
    await expect(rejectDispatchAutomationPlan('plan-2', 'Root cause not fixed')).resolves.toEqual(rejected);

    expect(client.post).toHaveBeenNthCalledWith(
      1,
      '/api/v1/analytics/dispatch-automation-plans',
      { recommendation_code: 'auto_retry_dead_letters' }
    );
    expect(client.post).toHaveBeenNthCalledWith(
      2,
      '/api/v1/analytics/dispatch-automation-plans/plan-1/approve'
    );
    expect(client.post).toHaveBeenNthCalledWith(
      3,
      '/api/v1/analytics/dispatch-automation-plans/plan-2/reject',
      { rejection_note: 'Root cause not fixed' }
    );
  });

  it('runs dispatch automation worker once with a guarded limit', async () => {
    const result = { run_id: 'run-1', claimed: 1, executed: 1, blocked: 0, failed: 0 };
    client.post = vi.fn().mockResolvedValueOnce({ data: result });

    await expect(runDispatchAutomationWorker(5)).resolves.toEqual(result);

    expect(client.post).toHaveBeenCalledWith(
      '/api/v1/analytics/dispatch-automation-worker/run',
      null,
      { params: { limit: 5 } }
    );
  });

  it('reads and updates dispatch automation worker schedule config', async () => {
    const config = { enabled: true, interval_minutes: 30, max_plans_per_run: 25 };
    client.get.mockResolvedValueOnce({ data: config });
    client.put = vi.fn().mockResolvedValueOnce({ data: config });

    await expect(fetchDispatchAutomationWorkerConfig()).resolves.toEqual(config);
    await expect(updateDispatchAutomationWorkerConfig(config)).resolves.toEqual(config);

    expect(client.get).toHaveBeenCalledWith('/api/v1/analytics/dispatch-automation-worker/config');
    expect(client.put).toHaveBeenCalledWith(
      '/api/v1/analytics/dispatch-automation-worker/config',
      config
    );
  });

  it('fetches dispatch automation worker diagnostics for owner dashboards', async () => {
    const diagnostics = {
      scheduler_enabled: false,
      scheduler_interval_seconds: 60,
      scheduler_tenant_limit: 25,
      tenant_config: { enabled: true, interval_minutes: 15, max_plans_per_run: 10 },
      approved_plan_count: 2,
      tenant_due_now: true,
      latest_scheduled_run: null,
    };
    client.get.mockResolvedValueOnce({ data: diagnostics });

    await expect(fetchDispatchAutomationWorkerDiagnostics()).resolves.toEqual(diagnostics);

    expect(client.get).toHaveBeenCalledWith(
      '/api/v1/analytics/dispatch-automation-worker/diagnostics'
    );
  });

  it('fetches dispatch automation worker fleet diagnostics for platform-admin dashboards', async () => {
    const diagnostics = {
      scheduler_enabled: false,
      scheduler_interval_seconds: 60,
      scheduler_tenant_limit: 25,
      total_tenants: 4,
      enabled_tenants: 3,
      backoff_tenants: 1,
      tenants: [{ tenant_id: 'tenant-1', due_now: true }],
    };
    client.get.mockResolvedValueOnce({ data: diagnostics });

    await expect(fetchDispatchAutomationWorkerFleetDiagnostics()).resolves.toEqual(diagnostics);

    expect(client.get).toHaveBeenCalledWith(
      '/api/v1/analytics/dispatch-automation-worker/fleet',
      { params: { include_tenants: true } }
    );
  });

  it('lists dispatch automation worker run audit rows', async () => {
    const runs = {
      items: [
        {
          id: 'run-1',
          trigger_type: 'manual',
          status: 'completed',
          limit: 5,
          claimed: 1,
          executed: 1,
          blocked: 0,
          failed: 0,
          created_at: '2026-05-25T10:00:00Z',
        },
      ],
    };
    client.get.mockResolvedValueOnce({ data: runs });

    await expect(fetchDispatchAutomationWorkerRuns(5)).resolves.toEqual(runs);

    expect(client.get).toHaveBeenCalledWith('/api/v1/analytics/dispatch-automation-worker/runs', {
      params: { limit: 5 },
    });
  });
});
