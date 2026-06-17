import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import CredentialManager, {
  buildCredentialPayload,
  clearCredentialSecret,
} from './CredentialManager';

describe('CredentialManager', () => {
  it('renders redacted credential previews without raw secrets', () => {
    const html = renderToStaticMarkup(
      <CredentialManager
        canManage
        credentials={[
          {
            id: 'cred-1',
            connector_key: 'http',
            name: 'Example API',
            auth_type: 'api_key_header',
            config_preview: {
              header_name: 'Authorization',
              header_value: '********oken',
            },
          },
        ]}
      />
    );

    expect(html).toContain('Example API');
    expect(html).toContain('********oken');
    expect(html).not.toContain('secret-token');
  });

  it('hides create and delete controls for viewers', () => {
    const html = renderToStaticMarkup(
      <CredentialManager
        canManage={false}
        credentials={[
          {
            id: 'cred-1',
            connector_key: 'http',
            name: 'Example API',
            auth_type: 'api_key_header',
            config_preview: { header_name: 'Authorization', header_value: '****' },
          },
        ]}
      />
    );

    expect(html).not.toContain('Create credential');
    expect(html).not.toContain('Delete');
  });

  it('builds create payload and clears secret field after create', () => {
    const form = {
      connectorKey: 'http',
      name: 'Example API',
      headerName: 'Authorization',
      headerValue: 'Bearer secret-token',
    };

    expect(buildCredentialPayload(form)).toEqual({
      connector_key: 'http',
      name: 'Example API',
      auth_type: 'api_key_header',
      config: {
        header_name: 'Authorization',
        header_value: 'Bearer secret-token',
      },
    });
    expect(clearCredentialSecret(form)).toEqual({
      connectorKey: 'http',
      name: 'Example API',
      headerName: 'Authorization',
      headerValue: '',
    });
  });
});
