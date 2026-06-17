import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import LogViewer from './LogViewer';

describe('LogViewer connector rendering', () => {
  it('renders connector metadata and sanitized errors', () => {
    const html = renderToStaticMarkup(
      <LogViewer
        currentStep={null}
        logs={[
          {
            step_number: 1,
            agent_name: 'HTTP Request',
            action: 'connector_error',
            node_type: 'connector',
            connector_key: 'http',
            action_key: 'request',
            retryable: false,
            sanitized_error: 'HTTP connector URL targets a private network.',
            tokens_used: 0,
            cost: 0,
            duration_ms: 4,
            output_data: {
              error: 'HTTP connector URL targets a private network.',
              headers: { Authorization: '****' },
            },
          },
        ]}
      />
    );

    expect(html).toContain('Connector');
    expect(html).toContain('http.request');
    expect(html).toContain('private network');
    expect(html).not.toContain('secret-token');
  });
});
