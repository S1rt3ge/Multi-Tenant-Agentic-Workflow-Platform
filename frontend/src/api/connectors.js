import client from './client';

export async function listConnectors() {
  const response = await client.get('/api/v1/connectors');
  return response.data;
}

export async function getConnector(connectorKey) {
  const response = await client.get(`/api/v1/connectors/${connectorKey}`);
  return response.data;
}

export async function createConnectorCredential(payload) {
  const response = await client.post('/api/v1/connector-credentials', payload);
  return response.data;
}

export async function listConnectorCredentials({ connectorKey } = {}) {
  const query = connectorKey
    ? `?connector_key=${encodeURIComponent(connectorKey)}`
    : '';
  const response = await client.get(`/api/v1/connector-credentials${query}`);
  return response.data;
}

export async function deleteConnectorCredential(credentialId) {
  await client.delete(`/api/v1/connector-credentials/${credentialId}`);
}

export async function createWorkflowTrigger(workflowId, payload) {
  const response = await client.post(
    `/api/v1/workflows/${workflowId}/triggers`,
    payload
  );
  return response.data;
}

export async function listWorkflowTriggers(workflowId) {
  const response = await client.get(`/api/v1/workflows/${workflowId}/triggers`);
  return response.data;
}
