import { renderToString } from 'react-dom/server';
import { describe, expect, it, vi } from 'vitest';

import DispatchRunbookPanel from './DispatchRunbookPanel';

describe('DispatchRunbookPanel', () => {
  it('renders incident handoff without secrets', () => {
    const html = renderToString(
      <DispatchRunbookPanel
        runbook={{
          severity: 'critical',
          summary: 'Dispatch incident handoff required',
          policy: { enabled: true, configured_channels: 1 },
          health: { dead_lettered_executions: 1, deferred_retries: 0 },
          alerts: [{ code: 'dead_lettered', severity: 'critical', title: 'Dead-letter queue needs review' }],
          recent_deliveries: [
            {
              id: 'delivery-1',
              alert_code: 'dead_lettered',
              status: 'failed',
              target_preview: 'https://8.8.8.8/dispatch?token=****',
            },
          ],
          recommended_actions: [
            { title: 'Review dead-letter queue', detail: 'Retry only after the root cause is fixed.' },
          ],
          acknowledgement: {
            acknowledged_by_email: 'owner@test.com',
            note: 'Taking ownership',
          },
          incident_history: [
            {
              id: 'ack-1',
              status: 'resolved',
              resolved_by_email: 'owner@test.com',
              resolution_note: 'Fixed downstream issue',
            },
          ],
        }}
        onExport={vi.fn()}
        onAcknowledge={vi.fn()}
        onResolve={vi.fn()}
        exporting={false}
        acknowledging={false}
        resolving={false}
      />
    );

    expect(html).toContain('Dispatch incident handoff required');
    expect(html).toContain('Review dead-letter queue');
    expect(html).toContain('owner@test.com');
    expect(html).toContain('Taking ownership');
    expect(html).toContain('Resolve');
    expect(html).toContain('Fixed downstream issue');
    expect(html).toContain('token=****');
    expect(html).not.toContain('secret-runbook-token');
    expect(html).not.toContain('secret-webhook-header');
    expect(html).not.toContain('secret-lead');
  });

  it('renders quiet state', () => {
    const html = renderToString(
      <DispatchRunbookPanel
        runbook={{
          severity: 'info',
          summary: 'No active dispatch incident',
          policy: { enabled: false, configured_channels: 0 },
          health: {},
          alerts: [],
          recent_deliveries: [],
          recommended_actions: [{ title: 'Continue monitoring dispatch health', detail: 'No handoff needed.' }],
          acknowledgement: null,
          incident_history: [],
        }}
        onExport={vi.fn()}
        onAcknowledge={vi.fn()}
        onResolve={vi.fn()}
        exporting={false}
        acknowledging={false}
        resolving={false}
      />
    );

    expect(html).toContain('No active dispatch incident');
    expect(html).toContain('Continue monitoring dispatch health');
  });
});
