import client from './client';

/**
 * Tool Registry API client functions.
 */

export async function createTool(data) {
  const resp = await client.post('/api/v1/tools/', data);
  return resp.data;
}

export async function listTools() {
  const resp = await client.get('/api/v1/tools/');
  return resp.data;
}

export async function updateTool(id, data) {
  const resp = await client.put(`/api/v1/tools/${id}`, data);
  return resp.data;
}

export async function deleteTool(id) {
  await client.delete(`/api/v1/tools/${id}`);
}

export async function testTool(id, testInput = null) {
  const body = testInput ? { test_input: testInput } : {};
  const resp = await client.post(`/api/v1/tools/${id}/test`, body);
  return resp.data;
}
