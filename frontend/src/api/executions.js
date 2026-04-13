import client from './client';

/**
 * Execution API client functions.
 */

/**
 * Start a workflow execution.
 * @param {string} workflowId - Workflow UUID
 * @param {object|null} inputData - Input data for the execution
 * @returns {Promise<{execution_id: string, status: string}>}
 */
export async function startExecution(workflowId, inputData = null) {
  const resp = await client.post(`/api/v1/workflows/${workflowId}/execute`, {
    input_data: inputData,
  });
  return resp.data;
}

/**
 * List executions with optional filters.
 * @param {object} params - Query parameters
 * @param {string} [params.workflowId] - Filter by workflow ID
 * @param {string} [params.status] - Filter by status
 * @param {number} [params.page=1] - Page number
 * @param {number} [params.perPage=20] - Items per page
 * @returns {Promise<{items: Array, total: number, page: number, per_page: number}>}
 */
export async function listExecutions({ workflowId, status, page = 1, perPage = 20 } = {}) {
  const params = new URLSearchParams();
  if (workflowId) params.append('workflow_id', workflowId);
  if (status) params.append('status_filter', status);
  params.append('page', String(page));
  params.append('per_page', String(perPage));

  const resp = await client.get(`/api/v1/executions?${params.toString()}`);
  return resp.data;
}

/**
 * Get execution details by ID.
 * @param {string} executionId
 * @returns {Promise<object>}
 */
export async function getExecution(executionId) {
  const resp = await client.get(`/api/v1/executions/${executionId}`);
  return resp.data;
}

/**
 * Get execution step logs.
 * @param {string} executionId
 * @returns {Promise<Array>}
 */
export async function getExecutionLogs(executionId) {
  const resp = await client.get(`/api/v1/executions/${executionId}/logs`);
  return resp.data;
}

/**
 * Cancel a running or pending execution.
 * @param {string} executionId
 * @returns {Promise<object>}
 */
export async function cancelExecution(executionId) {
  const resp = await client.post(`/api/v1/executions/${executionId}/cancel`);
  return resp.data;
}

/**
 * Get WebSocket URL for execution streaming.
 * @param {string} executionId
 * @returns {string}
 */
export function getExecutionStreamUrl(executionId) {
  const baseUrl = process.env.REACT_APP_WS_URL || 'ws://localhost:8000';
  return `${baseUrl}/api/v1/executions/${executionId}/stream`;
}
