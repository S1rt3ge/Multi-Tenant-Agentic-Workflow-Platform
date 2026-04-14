import client from './client';

/**
 * Analytics API client functions.
 */

export async function fetchOverview(period = 'month') {
  const resp = await client.get('/api/v1/analytics/overview', {
    params: { period },
  });
  return resp.data;
}

export async function fetchCostTimeline(days = 30) {
  const resp = await client.get('/api/v1/analytics/cost-timeline', {
    params: { days },
  });
  return resp.data;
}

export async function fetchWorkflowBreakdown(period = 'month') {
  const resp = await client.get('/api/v1/analytics/workflow-breakdown', {
    params: { period },
  });
  return resp.data;
}

export async function exportData({ format = 'csv', from, to } = {}) {
  const params = { format };
  if (from) params.from = from;
  if (to) params.to = to;

  const resp = await client.get('/api/v1/analytics/export', {
    params,
    responseType: format === 'csv' ? 'blob' : 'json',
  });

  if (format === 'csv') {
    // Trigger file download
    const blob = new Blob([resp.data], { type: 'text/csv' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'executions_export.csv';
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
    return null;
  }

  return resp.data;
}
