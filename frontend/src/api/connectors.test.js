import { beforeEach, describe, expect, it, vi } from 'vitest';

import client from './client';
import {
  createConnectorCredential,
  createWorkflowTrigger,
  deleteConnectorCredential,
  getConnector,
  listConnectorCredentials,
  listConnectors,
  listWorkflowTriggers,
} from './connectors';

vi.mock('./client', () => ({
  default: {
    delete: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
  },
}));

describe('connector API helpers', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('lists connectors', async () => {
    client.get.mockResolvedValueOnce({ data: { items: [{ key: 'http' }] } });

    await expect(listConnectors()).resolves.toEqual({ items: [{ key: 'http' }] });
    expect(client.get).toHaveBeenCalledWith('/api/v1/connectors');
  });

  it('gets a connector manifest', async () => {
    client.get.mockResolvedValueOnce({ data: { key: 'http' } });

    await expect(getConnector('http')).resolves.toEqual({ key: 'http' });
    expect(client.get).toHaveBeenCalledWith('/api/v1/connectors/http');
  });

  it('creates connector credentials', async () => {
    const payload = {
      connector_key: 'http',
      name: 'Example API',
      auth_type: 'api_key_header',
      config: {
        header_name: 'Authorization',
        header_value: 'Bearer secret-token',
      },
    };
    client.post.mockResolvedValueOnce({
      data: {
        id: 'cred-1',
        config_preview: { header_value: '********oken' },
      },
    });

    await expect(createConnectorCredential(payload)).resolves.toEqual({
      id: 'cred-1',
      config_preview: { header_value: '********oken' },
    });
    expect(client.post).toHaveBeenCalledWith('/api/v1/connector-credentials', payload);
  });

  it('lists connector credentials with optional connector filter', async () => {
    client.get.mockResolvedValueOnce({ data: { items: [{ id: 'cred-1' }] } });

    await expect(listConnectorCredentials({ connectorKey: 'http' })).resolves.toEqual({
      items: [{ id: 'cred-1' }],
    });
    expect(client.get).toHaveBeenCalledWith(
      '/api/v1/connector-credentials?connector_key=http'
    );
  });

  it('deletes connector credentials', async () => {
    client.delete.mockResolvedValueOnce({ data: null });

    await expect(deleteConnectorCredential('cred-1')).resolves.toBeUndefined();
    expect(client.delete).toHaveBeenCalledWith('/api/v1/connector-credentials/cred-1');
  });

  it('creates workflow triggers', async () => {
    client.post.mockResolvedValueOnce({ data: { id: 'trigger-1' } });

    await expect(
      createWorkflowTrigger('workflow-1', {
        trigger_type: 'webhook',
        config: { auth: 'none' },
      })
    ).resolves.toEqual({ id: 'trigger-1' });
    expect(client.post).toHaveBeenCalledWith(
      '/api/v1/workflows/workflow-1/triggers',
      {
        trigger_type: 'webhook',
        config: { auth: 'none' },
      }
    );
  });

  it('lists workflow triggers', async () => {
    client.get.mockResolvedValueOnce({ data: { items: [{ id: 'trigger-1' }] } });

    await expect(listWorkflowTriggers('workflow-1')).resolves.toEqual({
      items: [{ id: 'trigger-1' }],
    });
    expect(client.get).toHaveBeenCalledWith('/api/v1/workflows/workflow-1/triggers');
  });
});
