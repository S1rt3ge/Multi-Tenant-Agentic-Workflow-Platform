import { renderToString } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import DispatchIncidentAnalyticsPanel from './DispatchIncidentAnalyticsPanel';

describe('DispatchIncidentAnalyticsPanel', () => {
  it('renders aggregate incident SLA telemetry without secrets', () => {
    const html = renderToString(
      <DispatchIncidentAnalyticsPanel
        analytics={{
          window_days: 7,
          sla_minutes: 60,
          total_incidents: 3,
          resolved_incidents: 2,
          open_incidents: 1,
          sla_breaches: 2,
          sla_breach_rate: 66.7,
          avg_resolution_minutes: 55,
          trends: [
            { day: '2026-05-17', acknowledged: 1, resolved: 1, open: 0, sla_breaches: 0 },
            { day: '2026-05-18', acknowledged: 2, resolved: 1, open: 1, sla_breaches: 2 },
          ],
          by_severity: [
            {
              severity: 'critical',
              total_incidents: 1,
              resolved_incidents: 1,
              open_incidents: 0,
              sla_breaches: 1,
              avg_resolution_minutes: 90,
            },
            {
              severity: 'warning',
              total_incidents: 2,
              resolved_incidents: 1,
              open_incidents: 1,
              sla_breaches: 1,
              avg_resolution_minutes: 20,
            },
          ],
        }}
      />
    );

    expect(html).toContain('Incident analytics');
    expect(html).toContain('SLA breaches');
    expect(html).toContain('66.7%');
    expect(html).toContain('critical');
    expect(html).toContain('warning');
    expect(html).not.toContain('secret-resolution-token');
    expect(html).not.toContain('owner@test.com');
    expect(html).not.toContain('resolver@test.com');
  });
});
