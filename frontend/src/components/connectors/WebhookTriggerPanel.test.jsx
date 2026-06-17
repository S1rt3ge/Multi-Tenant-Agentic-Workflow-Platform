import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import WebhookTriggerPanel from './WebhookTriggerPanel';

describe('WebhookTriggerPanel', () => {
  it('renders existing webhook trigger URLs', () => {
    const html = renderToStaticMarkup(
      <WebhookTriggerPanel
        canManage
        triggers={[
          {
            id: 'trigger-1',
            trigger_type: 'webhook',
            webhook_url: 'http://localhost:8001/api/v1/webhooks/public-id',
            is_active: true,
          },
        ]}
      />
    );

    expect(html).toContain('Webhook triggers');
    expect(html).toContain('http://localhost:8001/api/v1/webhooks/public-id');
    expect(html).toContain('Create webhook');
  });

  it('lets viewers list triggers but not create them', () => {
    const html = renderToStaticMarkup(
      <WebhookTriggerPanel
        canManage={false}
        triggers={[
          {
            id: 'trigger-1',
            trigger_type: 'webhook',
            webhook_url: 'http://localhost:8001/api/v1/webhooks/public-id',
            is_active: true,
          },
        ]}
      />
    );

    expect(html).toContain('http://localhost:8001/api/v1/webhooks/public-id');
    expect(html).not.toContain('Create webhook');
  });
});
