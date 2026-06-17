import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import DispatchHealthPanel from './DispatchHealthPanel';

describe('DispatchHealthPanel', () => {
  it('renders dispatch health metrics and alerts without raw webhook data', () => {
    const html = renderToStaticMarkup(
      <DispatchHealthPanel
        health={{
          paused_workflows: 1,
          throttled_triggers: 2,
          pending_dispatches: 3,
          deferred_retries: 1,
          dead_lettered_executions: 1,
          manual_retries: 4,
          alerts: [
            {
              code: 'dead_lettered',
              severity: 'critical',
              title: 'Dead-letter queue needs review',
              message: '1 webhook dispatch is dead-lettered.',
              count: 1,
            },
          ],
        }}
      />
    );

    expect(html).toContain('Dispatch health');
    expect(html).toContain('Paused workflows');
    expect(html).toContain('Throttled triggers');
    expect(html).toContain('Pending dispatches');
    expect(html).toContain('Dead-lettered');
    expect(html).toContain('Manual retries');
    expect(html).toContain('Dead-letter queue needs review');
    expect(html).not.toContain('secret-webhook-header');
    expect(html).not.toContain('lead-123');
  });

  it('renders quiet empty state when there are no dispatch alerts', () => {
    const html = renderToStaticMarkup(
      <DispatchHealthPanel
        health={{
          paused_workflows: 0,
          throttled_triggers: 0,
          pending_dispatches: 0,
          deferred_retries: 0,
          dead_lettered_executions: 0,
          manual_retries: 0,
          alerts: [],
        }}
      />
    );

    expect(html).toContain('No active dispatch alerts');
    expect(html).not.toContain('Dead-letter queue needs review');
  });

  it('renders nothing before health data is loaded', () => {
    const html = renderToStaticMarkup(<DispatchHealthPanel health={null} />);

    expect(html).toBe('');
  });
});
