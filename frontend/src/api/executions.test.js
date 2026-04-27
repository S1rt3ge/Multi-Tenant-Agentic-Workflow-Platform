import { beforeEach, describe, expect, it, vi } from 'vitest';

import { getExecutionStreamUrl } from './executions';


describe('execution API helpers', () => {
  beforeEach(() => {
    vi.stubGlobal('window', {
      __GRAPHPILOT_CONFIG__: {},
      location: { protocol: 'https:', host: 'app.example.com' },
    });
  });

  it('derives websocket URL from runtime API URL', () => {
    window.__GRAPHPILOT_CONFIG__ = { VITE_API_URL: 'https://api.example.com' };

    expect(getExecutionStreamUrl('exec-1')).toBe('wss://api.example.com/api/v1/executions/exec-1/stream');
  });

  it('allows runtime websocket override', () => {
    window.__GRAPHPILOT_CONFIG__ = {
      VITE_API_URL: 'https://api.example.com',
      VITE_WS_URL: 'wss://ws.example.com',
    };

    expect(getExecutionStreamUrl('exec-1')).toBe('wss://ws.example.com/api/v1/executions/exec-1/stream');
  });
});
