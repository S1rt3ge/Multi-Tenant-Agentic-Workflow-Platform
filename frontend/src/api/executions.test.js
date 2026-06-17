import { beforeEach, describe, expect, it, vi } from 'vitest';

import client from './client';
import {
  applyFixSuggestion,
  diagnoseExecution,
  dismissFixSuggestion,
  getExecutionStreamUrl,
  listWorkflowDispatchExecutions,
  listFixSuggestions,
  replayFixSuggestion,
  retryExecution,
} from './executions';

vi.mock('./client', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
  },
}));

describe('execution API helpers', () => {
  beforeEach(() => {
    vi.clearAllMocks();
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

describe('workflow doctor API helpers', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('diagnoses an execution with force disabled by default', async () => {
    client.post.mockResolvedValueOnce({ data: { items: [], total: 0 } });

    await expect(diagnoseExecution('exec-1')).resolves.toEqual({ items: [], total: 0 });
    expect(client.post).toHaveBeenCalledWith('/api/v1/executions/exec-1/diagnose', {
      force: false,
    });
  });

  it('lists fix suggestions for an execution', async () => {
    client.get.mockResolvedValueOnce({ data: { items: [{ id: 'sug-1' }], total: 1 } });

    await expect(listFixSuggestions('exec-1')).resolves.toEqual({
      items: [{ id: 'sug-1' }],
      total: 1,
    });
    expect(client.get).toHaveBeenCalledWith('/api/v1/executions/exec-1/fix-suggestions');
  });

  it('replays, applies, and dismisses a suggestion', async () => {
    client.post
      .mockResolvedValueOnce({ data: { status: 'passed' } })
      .mockResolvedValueOnce({ data: { status: 'applied', retry_execution_id: 'exec-2' } })
      .mockResolvedValueOnce({ data: { status: 'dismissed' } });

    await expect(replayFixSuggestion('sug-1')).resolves.toEqual({ status: 'passed' });
    await expect(applyFixSuggestion('sug-1')).resolves.toEqual({
      status: 'applied',
      retry_execution_id: 'exec-2',
    });
    await expect(dismissFixSuggestion('sug-1')).resolves.toEqual({ status: 'dismissed' });

    expect(client.post).toHaveBeenNthCalledWith(
      1,
      '/api/v1/fix-suggestions/sug-1/replay',
      { mode: 'validation_only' }
    );
    expect(client.post).toHaveBeenNthCalledWith(
      2,
      '/api/v1/fix-suggestions/sug-1/apply',
      { retry: true }
    );
    expect(client.post).toHaveBeenNthCalledWith(
      3,
      '/api/v1/fix-suggestions/sug-1/dismiss'
    );
  });
});

describe('dispatch queue API helpers', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('lists workflow dispatch executions through the existing executions endpoint', async () => {
    client.get.mockResolvedValueOnce({
      data: { items: [{ id: 'exec-1' }], total: 1, page: 1, per_page: 20 },
    });

    await expect(listWorkflowDispatchExecutions('workflow-1')).resolves.toEqual({
      items: [{ id: 'exec-1' }],
      total: 1,
      page: 1,
      per_page: 20,
    });

    expect(client.get).toHaveBeenCalledWith(
      '/api/v1/executions?workflow_id=workflow-1&page=1&per_page=20'
    );
  });

  it('passes status filter and pagination to the workflow dispatch execution query', async () => {
    client.get.mockResolvedValueOnce({
      data: { items: [{ id: 'exec-dead-1' }], total: 1, page: 2, per_page: 10 },
    });

    await expect(
      listWorkflowDispatchExecutions('workflow-1', {
        status: 'failed',
        page: 2,
        perPage: 10,
      })
    ).resolves.toEqual({
      items: [{ id: 'exec-dead-1' }],
      total: 1,
      page: 2,
      per_page: 10,
    });

    expect(client.get).toHaveBeenCalledWith(
      '/api/v1/executions?workflow_id=workflow-1&status_filter=failed&page=2&per_page=10'
    );
  });

  it('retries a dead-letter execution through the execution retry endpoint', async () => {
    client.post.mockResolvedValueOnce({
      data: {
        execution_id: 'exec-retry-4',
        source_execution_id: 'exec-dead-3',
        status: 'pending',
      },
    });

    await expect(retryExecution('exec-dead-3')).resolves.toEqual({
      execution_id: 'exec-retry-4',
      source_execution_id: 'exec-dead-3',
      status: 'pending',
    });

    expect(client.post).toHaveBeenCalledWith('/api/v1/executions/exec-dead-3/retry');
  });
});
