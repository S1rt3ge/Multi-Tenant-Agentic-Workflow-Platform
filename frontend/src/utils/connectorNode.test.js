import { describe, expect, it } from 'vitest';

import {
  buildHttpConnectorNodeData,
  parseJsonField,
  validateHttpConnectorConfig,
} from './connectorNode';

describe('connector node helpers', () => {
  it('builds M9-compatible HTTP connector node data', () => {
    const data = buildHttpConnectorNodeData({
      label: 'Fetch Lead',
      url: 'https://example.com/api/leads',
      method: 'POST',
      credentialId: 'cred-1',
      headersJson: '{"Accept":"application/json"}',
      queryJson: '{"limit":10}',
      bodyJson: '{"lead_id":"123"}',
      timeoutSeconds: 12,
    });

    expect(data).toEqual({
      label: 'Fetch Lead',
      connector_key: 'http',
      action_key: 'request',
      credential_id: 'cred-1',
      input: {
        url: 'https://example.com/api/leads',
        method: 'POST',
        headers: { Accept: 'application/json' },
        query: { limit: 10 },
        body: { lead_id: '123' },
        timeout_seconds: 12,
      },
    });
  });

  it('validates URL, method, JSON objects, and timeout', () => {
    const errors = validateHttpConnectorConfig({
      url: '',
      method: 'TRACE',
      headersJson: '[]',
      queryJson: '{',
      bodyJson: '{"ok":true}',
      timeoutSeconds: 0,
    });

    expect(errors).toEqual({
      url: 'URL is required.',
      method: 'Method is not supported.',
      headersJson: 'Headers must be a JSON object.',
      queryJson: 'Query must be valid JSON.',
      timeoutSeconds: 'Timeout must be between 1 and 120 seconds.',
    });
  });

  it('parses blank object fields as empty objects', () => {
    expect(parseJsonField('', { requireObject: true })).toEqual({
      ok: true,
      value: {},
    });
  });
});
