import client from './client';

/**
 * Workflow API client functions.
 */

export async function createWorkflow(data) {
  const resp = await client.post('/api/v1/workflows/', data);
  return resp.data;
}

export async function listWorkflows({ page = 1, perPage = 20, search = '' } = {}) {
  const params = { page, per_page: perPage };
  if (search) params.search = search;
  const resp = await client.get('/api/v1/workflows/', { params });
  return resp.data;
}

export async function getWorkflow(id) {
  const resp = await client.get(`/api/v1/workflows/${id}`);
  return resp.data;
}

export async function updateWorkflow(id, data) {
  const resp = await client.put(`/api/v1/workflows/${id}`, data);
  return resp.data;
}

export async function duplicateWorkflow(id) {
  const resp = await client.post(`/api/v1/workflows/${id}/duplicate`);
  return resp.data;
}

export async function deleteWorkflow(id) {
  await client.delete(`/api/v1/workflows/${id}`);
}
