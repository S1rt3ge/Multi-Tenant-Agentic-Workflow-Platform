import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import DispatchAlertPolicyPanel from './DispatchAlertPolicyPanel';

describe('DispatchAlertPolicyPanel', () => {
  const policy = {
    enabled: true,
    channels: [{ type: 'email', target: 'ops@example.com', enabled: true }],
    severities: ['critical', 'warning'],
    alert_codes: ['dead_lettered', 'trigger_throttled'],
    cooldown_minutes: 15,
  };

  const preview = {
    dry_run: true,
    policy_enabled: true,
    alerts: [
      {
        code: 'dead_lettered',
        severity: 'critical',
        title: 'Dead-letter queue needs review',
        message: '1 webhook dispatch is dead-lettered.',
        count: 1,
      },
    ],
    routes: [
      {
        channel_type: 'email',
        target: 'ops@example.com',
        alert_codes: ['dead_lettered'],
      },
    ],
  };

  it('renders policy routing and dry-run preview', () => {
    const html = renderToStaticMarkup(
      <DispatchAlertPolicyPanel policy={policy} preview={preview} />
    );

    expect(html).toContain('Alert routing');
    expect(html).toContain('Enabled');
    expect(html).toContain('ops@example.com');
    expect(html).toContain('Dry-run preview');
    expect(html).toContain('Dead-letter queue needs review');
    expect(html).toContain('dead_lettered');
  });

  it('renders disabled policy without planned routes', () => {
    const html = renderToStaticMarkup(
      <DispatchAlertPolicyPanel
        policy={{ ...policy, enabled: false, channels: [] }}
        preview={{ ...preview, policy_enabled: false, routes: [] }}
      />
    );

    expect(html).toContain('Disabled');
    expect(html).toContain('No routes planned');
  });

  it('renders nothing until policy and preview are loaded', () => {
    const html = renderToStaticMarkup(
      <DispatchAlertPolicyPanel policy={null} preview={null} />
    );

    expect(html).toBe('');
  });
});
