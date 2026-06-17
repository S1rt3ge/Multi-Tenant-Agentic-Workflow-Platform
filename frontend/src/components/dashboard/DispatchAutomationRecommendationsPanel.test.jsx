import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import DispatchAutomationRecommendationsPanel from './DispatchAutomationRecommendationsPanel';

describe('DispatchAutomationRecommendationsPanel', () => {
  const recommendations = {
    dry_run: true,
    window_hours: 24,
    sla_minutes: 60,
    recommendation_count: 2,
    automation_ready_count: 1,
    recommendations: [
      {
        code: 'auto_retry_dead_letters',
        priority: 'critical',
        title: 'Automate eligible dead-letter retry triage',
        rationale: 'Dead-letter queue has work waiting for operator review.',
        suggested_action: 'Create an approval-gated retry plan for eligible dead-lettered dispatches.',
        automation_type: 'approval_gated_retry',
        confidence: 0.91,
        evidence: ['1 dead-lettered webhook dispatch in the last 24 hours'],
        blocked_by: [],
      },
      {
        code: 'setup_alert_routing',
        priority: 'warning',
        title: 'Enable automated alert routing',
        rationale: 'Alert routing is disabled.',
        suggested_action: 'Configure a credential-backed alert route before enabling automated escalation.',
        automation_type: 'alert_routing_setup',
        confidence: 0.74,
        evidence: ['Dispatch alert policy is disabled'],
        blocked_by: ['No active alert routing policy'],
      },
    ],
  };

  it('renders dry-run automation recommendations without secrets', () => {
    const html = renderToString(
      <DispatchAutomationRecommendationsPanel
        recommendations={recommendations}
      />
    );

    expect(html).toContain('Automation recommendations');
    expect(html).toContain('dry-run');
    expect(html).toContain('approval_gated_retry');
    expect(html).toContain('Automate eligible dead-letter retry triage');
    expect(html).toContain('No active alert routing policy');
    expect(html).not.toContain('secret-workflow-token');
    expect(html).not.toContain('secret-webhook-header');
    expect(html).not.toContain('owner@test.com');
  });

  it('renders owner plan controls and sanitized execution history', () => {
    const html = renderToString(
      <DispatchAutomationRecommendationsPanel
        recommendations={recommendations}
        userRole="owner"
        plans={{
          items: [
            {
              id: 'plan-pending',
              recommendation_code: 'auto_retry_dead_letters',
              automation_type: 'approval_gated_retry',
              status: 'pending_approval',
              priority: 'critical',
              title: 'Automate eligible dead-letter retry triage',
              created_at: '2026-05-22T09:00:00Z',
              requested_by_email: 'owner@test.com',
              execution_result: {},
            },
            {
              id: 'plan-approved',
              recommendation_code: 'auto_resume_guard',
              automation_type: 'resume_guard',
              status: 'approved',
              priority: 'warning',
              title: 'Resume dispatch safely',
              created_at: '2026-05-22T08:30:00Z',
              execution_result: {},
            },
            {
              id: 'plan-executed',
              recommendation_code: 'auto_resume_guard',
              automation_type: 'resume_guard',
              status: 'executed',
              priority: 'warning',
              title: 'Resume dispatch safely',
              created_at: '2026-05-22T08:00:00Z',
              executed_at: '2026-05-22T08:05:00Z',
              approved_by_email: 'owner@test.com',
              rejected_by_email: null,
              execution_result: {
                action: 'resume_guard',
                resumed_workflows: 1,
                payload: 'secret-webhook-payload',
                headers: { authorization: 'secret-webhook-header' },
              },
            },
          ],
        }}
        workerResult={{ claimed: 1, executed: 1, blocked: 0, failed: 0 }}
        workerConfig={{ enabled: true, interval_minutes: 30, max_plans_per_run: 25 }}
        workerRuns={{
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
        }}
      />
    );

    expect(html).toContain('Create plan');
    expect(html).toContain('Run worker');
    expect(html).toContain('claimed: 1');
    expect(html).toContain('executed: 1');
    expect(html).toContain('Approve');
    expect(html).toContain('Reject');
    expect(html).toContain('Automation plans');
    expect(html).toContain('Worker schedule');
    expect(html).toContain('Every 30 min');
    expect(html).toContain('Max 25 plans');
    expect(html).toContain('Disable schedule');
    expect(html).toContain('Recent worker runs');
    expect(html).toContain('manual');
    expect(html).toContain('completed');
    expect(html).toContain('pending_approval');
    expect(html).toContain('executed');
    expect(html).toContain('resumed_workflows');
    expect(html).toContain('1');
    expect(html).not.toContain('owner@test.com');
    expect(html).not.toContain('secret-webhook-payload');
    expect(html).not.toContain('secret-webhook-header');
  });

  it('renders viewer history without mutation controls', () => {
    const html = renderToString(
      <DispatchAutomationRecommendationsPanel
        recommendations={recommendations}
        userRole="viewer"
        workerConfig={{ enabled: true, interval_minutes: 30, max_plans_per_run: 25 }}
        workerRuns={{
          items: [
            {
              id: 'run-1',
              trigger_type: 'scheduled',
              status: 'completed',
              limit: 25,
              claimed: 0,
              executed: 0,
              blocked: 0,
              failed: 0,
              created_at: '2026-05-25T10:00:00Z',
            },
          ],
        }}
        plans={{
          items: [
            {
              id: 'plan-pending',
              recommendation_code: 'auto_retry_dead_letters',
              automation_type: 'approval_gated_retry',
              status: 'pending_approval',
              priority: 'critical',
              title: 'Automate eligible dead-letter retry triage',
              created_at: '2026-05-22T09:00:00Z',
              execution_result: {},
            },
          ],
        }}
      />
    );

    expect(html).toContain('Automation plans');
    expect(html).toContain('Worker schedule');
    expect(html).toContain('Every 30 min');
    expect(html).toContain('Recent worker runs');
    expect(html).toContain('scheduled');
    expect(html).toContain('pending_approval');
    expect(html).not.toContain('Create plan');
    expect(html).not.toContain('Run worker');
    expect(html).not.toContain('Disable schedule');
    expect(html).not.toContain('Approve');
    expect(html).not.toContain('Reject');
  });
});
