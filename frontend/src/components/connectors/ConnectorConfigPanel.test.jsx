import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import ConnectorConfigPanel from './ConnectorConfigPanel';

describe('ConnectorConfigPanel', () => {
  it('renders HTTP request configuration controls and selected credential', () => {
    const html = renderToStaticMarkup(
      <ConnectorConfigPanel
        node={{
          id: 'http-1',
          data: {
            label: 'Fetch Lead',
            connector_key: 'http',
            action_key: 'request',
            credential_id: 'cred-1',
            input: {
              url: 'https://example.com/api',
              method: 'GET',
              headers: { Accept: 'application/json' },
            },
          },
        }}
        credentials={[
          {
            id: 'cred-1',
            name: 'Example API',
            config_preview: { header_value: '********oken' },
          },
        ]}
      />
    );

    expect(html).toContain('HTTP Request');
    expect(html).toContain('Fetch Lead');
    expect(html).toContain('https://example.com/api');
    expect(html).toContain('Example API');
  });

  it('renders validation errors near connector fields', () => {
    const html = renderToStaticMarkup(
      <ConnectorConfigPanel
        node={{ id: 'http-1', data: { input: {} } }}
        validationErrors={{
          url: 'URL is required.',
          headersJson: 'Headers must be a JSON object.',
        }}
      />
    );

    expect(html).toContain('URL is required.');
    expect(html).toContain('Headers must be a JSON object.');
  });
});
