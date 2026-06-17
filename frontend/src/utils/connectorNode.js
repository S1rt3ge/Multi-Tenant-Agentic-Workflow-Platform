export const HTTP_METHODS = ['GET', 'POST', 'PUT', 'PATCH', 'DELETE'];

export function parseJsonField(value, { requireObject = false, emptyValue = {} } = {}) {
  const text = String(value ?? '').trim();
  if (!text) {
    return { ok: true, value: emptyValue };
  }

  try {
    const parsed = JSON.parse(text);
    if (
      requireObject &&
      (parsed === null || Array.isArray(parsed) || typeof parsed !== 'object')
    ) {
      return { ok: false, error: 'Expected a JSON object.' };
    }
    return { ok: true, value: parsed };
  } catch {
    return { ok: false, error: 'Invalid JSON.' };
  }
}

export function validateHttpConnectorConfig(form) {
  const errors = {};
  const method = String(form.method || '').toUpperCase();
  const timeout = Number(form.timeoutSeconds);
  const headers = parseJsonField(form.headersJson, { requireObject: true });
  const query = parseJsonField(form.queryJson, { requireObject: true });
  const body = parseJsonField(form.bodyJson, {
    requireObject: false,
    emptyValue: null,
  });

  if (!String(form.url || '').trim()) {
    errors.url = 'URL is required.';
  }
  if (!HTTP_METHODS.includes(method)) {
    errors.method = 'Method is not supported.';
  }
  if (!headers.ok) {
    errors.headersJson =
      headers.error === 'Expected a JSON object.'
        ? 'Headers must be a JSON object.'
        : 'Headers must be valid JSON.';
  }
  if (!query.ok) {
    errors.queryJson =
      query.error === 'Expected a JSON object.'
        ? 'Query must be a JSON object.'
        : 'Query must be valid JSON.';
  }
  if (!body.ok) {
    errors.bodyJson = 'Body must be valid JSON.';
  }
  if (!Number.isFinite(timeout) || timeout < 1 || timeout > 120) {
    errors.timeoutSeconds = 'Timeout must be between 1 and 120 seconds.';
  }

  return errors;
}

export function buildHttpConnectorNodeData(form) {
  const headers = parseJsonField(form.headersJson, { requireObject: true });
  const query = parseJsonField(form.queryJson, { requireObject: true });
  const body = parseJsonField(form.bodyJson, {
    requireObject: false,
    emptyValue: null,
  });

  return {
    label: String(form.label || 'HTTP Request').trim() || 'HTTP Request',
    connector_key: 'http',
    action_key: 'request',
    credential_id: form.credentialId || null,
    input: {
      url: String(form.url || '').trim(),
      method: String(form.method || 'GET').toUpperCase(),
      headers: headers.ok ? headers.value : {},
      query: query.ok ? query.value : {},
      body: body.ok ? body.value : null,
      timeout_seconds: Number(form.timeoutSeconds || 20),
    },
  };
}

export function connectorNodeToForm(node) {
  const data = node?.data || {};
  const input = data.input || {};

  return {
    label: data.label || 'HTTP Request',
    url: input.url || '',
    method: input.method || 'GET',
    credentialId: data.credential_id || '',
    headersJson: JSON.stringify(input.headers || {}, null, 2),
    queryJson: JSON.stringify(input.query || {}, null, 2),
    bodyJson:
      input.body === undefined || input.body === null
        ? ''
        : JSON.stringify(input.body, null, 2),
    timeoutSeconds: input.timeout_seconds || 20,
  };
}

export function createHttpConnectorNode(id, position) {
  return {
    id,
    type: 'connector',
    position,
    data: buildHttpConnectorNodeData({
      label: 'HTTP Request',
      url: '',
      method: 'GET',
      credentialId: '',
      headersJson: '{"Accept":"application/json"}',
      queryJson: '{}',
      bodyJson: '',
      timeoutSeconds: 20,
    }),
  };
}
