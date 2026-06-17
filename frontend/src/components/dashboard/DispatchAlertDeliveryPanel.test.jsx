import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import DispatchAlertDeliveryPanel from './DispatchAlertDeliveryPanel';

describe('DispatchAlertDeliveryPanel', () => {
  it('renders channel previews and delivery audit without secrets', () => {
    const html = renderToStaticMarkup(
      <DispatchAlertDeliveryPanel
        channels={[
          {
            id: 'channel-1',
            name: 'Ops webhook',
            channel_type: 'webhook',
            config_preview: {
              url: 'https://hooks.example.com/dispatch',
              headers: { Authorization: '****' },
            },
            is_active: true,
          },
        ]}
        deliveries={[
          {
            id: 'delivery-1',
            alert_code: 'dead_lettered',
            channel_type: 'webhook',
            target_preview: 'https://hooks.example.com/dispatch',
            status: 'delivered',
            status_code: 202,
          },
        ]}
      />
    );

    expect(html).toContain('Delivery adapters');
    expect(html).toContain('Ops webhook');
    expect(html).toContain('https://hooks.example.com/dispatch');
    expect(html).toContain('dead_lettered');
    expect(html).toContain('delivered');
    expect(html).not.toContain('secret-delivery-token');
    expect(html).not.toContain('secret-webhook-header');
  });

  it('renders empty state for no configured delivery channels', () => {
    const html = renderToStaticMarkup(
      <DispatchAlertDeliveryPanel channels={[]} deliveries={[]} />
    );

    expect(html).toContain('No delivery channels configured');
    expect(html).toContain('No delivery attempts yet');
  });

  it('renders nothing before data is loaded', () => {
    const html = renderToStaticMarkup(
      <DispatchAlertDeliveryPanel channels={null} deliveries={null} />
    );

    expect(html).toBe('');
  });
});
