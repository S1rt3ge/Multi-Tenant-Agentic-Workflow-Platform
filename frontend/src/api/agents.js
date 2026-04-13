import client from './client';

/**
 * Agent Config API client functions.
 * All endpoints are scoped under a specific workflow.
 */

export async function listAgents(workflowId) {
  const resp = await client.get(`/api/v1/workflows/${workflowId}/agents`);
  return resp.data;
}

export async function createAgent(workflowId, data) {
  const resp = await client.post(`/api/v1/workflows/${workflowId}/agents`, data);
  return resp.data;
}

export async function updateAgent(workflowId, agentId, data) {
  const resp = await client.put(
    `/api/v1/workflows/${workflowId}/agents/${agentId}`,
    data
  );
  return resp.data;
}

export async function deleteAgent(workflowId, agentId) {
  await client.delete(`/api/v1/workflows/${workflowId}/agents/${agentId}`);
}
