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

export async function fetchDispatchHealth(windowHours = 24) {
  const resp = await client.get('/api/v1/analytics/dispatch-health', {
    params: { window_hours: windowHours },
  });
  return resp.data;
}

export async function fetchDispatchAlertPolicy() {
  const resp = await client.get('/api/v1/analytics/dispatch-alert-policy');
  return resp.data;
}

export async function updateDispatchAlertPolicy(policy) {
  const resp = await client.put('/api/v1/analytics/dispatch-alert-policy', policy);
  return resp.data;
}

export async function previewDispatchAlertPolicy(windowHours = 24) {
  const resp = windowHours === 24
    ? await client.post('/api/v1/analytics/dispatch-alert-policy/preview')
    : await client.post('/api/v1/analytics/dispatch-alert-policy/preview', null, {
      params: { window_hours: windowHours },
    });
  return resp.data;
}

export async function createDispatchAlertChannel(channel) {
  const resp = await client.post('/api/v1/analytics/dispatch-alert-channels', channel);
  return resp.data;
}

export async function fetchDispatchAlertChannels() {
  const resp = await client.get('/api/v1/analytics/dispatch-alert-channels');
  return resp.data;
}

export async function deliverDispatchAlerts() {
  const resp = await client.post('/api/v1/analytics/dispatch-alert-deliveries');
  return resp.data;
}

export async function fetchDispatchAlertDeliveries() {
  const resp = await client.get('/api/v1/analytics/dispatch-alert-deliveries');
  return resp.data;
}

export async function fetchDispatchRunbook(windowHours = 24) {
  const resp = await client.get('/api/v1/analytics/dispatch-runbook', {
    params: { window_hours: windowHours, format: 'json' },
  });
  return resp.data;
}

export async function exportDispatchRunbook(windowHours = 24) {
  const resp = await client.get('/api/v1/analytics/dispatch-runbook', {
    params: { window_hours: windowHours, format: 'markdown' },
    responseType: 'blob',
  });
  const body = resp.data instanceof Blob ? await resp.data.text() : resp.data;

  if (typeof document !== 'undefined' && typeof window !== 'undefined') {
    const blob = new Blob([body], { type: 'text/markdown' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'dispatch_runbook.md';
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  }

  return body;
}

export async function fetchDispatchIncidentAcknowledgement() {
  const resp = await client.get('/api/v1/analytics/dispatch-incident-acknowledgement');
  return resp.data;
}

export async function acknowledgeDispatchIncident(note = '') {
  const resp = await client.post('/api/v1/analytics/dispatch-incident-acknowledgement', {
    note,
  });
  return resp.data;
}

export async function resolveDispatchIncident(resolutionNote = '') {
  const resp = await client.post('/api/v1/analytics/dispatch-incident-acknowledgement/resolve', {
    resolution_note: resolutionNote,
  });
  return resp.data;
}

export async function fetchDispatchIncidentHistory() {
  const resp = await client.get('/api/v1/analytics/dispatch-incident-history');
  return resp.data;
}

export async function fetchDispatchIncidentAnalytics(days = 30, slaMinutes = 60) {
  const resp = await client.get('/api/v1/analytics/dispatch-incident-analytics', {
    params: { days, sla_minutes: slaMinutes },
  });
  return resp.data;
}

export async function fetchDispatchControlRecommendations(windowHours = 24, slaMinutes = 60) {
  const resp = await client.get('/api/v1/analytics/dispatch-control-recommendations', {
    params: { window_hours: windowHours, sla_minutes: slaMinutes },
  });
  return resp.data;
}

export async function fetchDispatchAutomationPlans(limit = 20) {
  const resp = await client.get('/api/v1/analytics/dispatch-automation-plans', {
    params: { limit },
  });
  return resp.data;
}

export async function createDispatchAutomationPlan(recommendationCode) {
  const resp = await client.post('/api/v1/analytics/dispatch-automation-plans', {
    recommendation_code: recommendationCode,
  });
  return resp.data;
}

export async function approveDispatchAutomationPlan(planId) {
  const resp = await client.post(`/api/v1/analytics/dispatch-automation-plans/${planId}/approve`);
  return resp.data;
}

export async function rejectDispatchAutomationPlan(planId, rejectionNote = 'Rejected from dashboard') {
  const resp = await client.post(`/api/v1/analytics/dispatch-automation-plans/${planId}/reject`, {
    rejection_note: rejectionNote,
  });
  return resp.data;
}

export async function fetchDispatchAutomationWorkerConfig() {
  const resp = await client.get('/api/v1/analytics/dispatch-automation-worker/config');
  return resp.data;
}

export async function updateDispatchAutomationWorkerConfig(config) {
  const resp = await client.put('/api/v1/analytics/dispatch-automation-worker/config', config);
  return resp.data;
}

export async function fetchDispatchAutomationWorkerRuns(limit = 20) {
  const resp = await client.get('/api/v1/analytics/dispatch-automation-worker/runs', {
    params: { limit },
  });
  return resp.data;
}

export async function fetchDispatchAutomationWorkerDiagnostics() {
  const resp = await client.get('/api/v1/analytics/dispatch-automation-worker/diagnostics');
  return resp.data;
}

export async function fetchDispatchAutomationWorkerFleetDiagnostics(includeTenants = true) {
  const resp = await client.get('/api/v1/analytics/dispatch-automation-worker/fleet', {
    params: { include_tenants: includeTenants },
  });
  return resp.data;
}

export async function runDispatchAutomationWorker(limit = 10) {
  const resp = await client.post('/api/v1/analytics/dispatch-automation-worker/run', null, {
    params: { limit },
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

  if (format === 'json') {
    const body = JSON.stringify(resp.data, null, 2);
    const blob = new Blob([body], { type: 'application/json' });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'executions_export.json';
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
    return resp.data;
  }

  return resp.data;
}
