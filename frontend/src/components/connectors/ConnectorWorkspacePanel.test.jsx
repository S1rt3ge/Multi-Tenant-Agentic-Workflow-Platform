import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import ConnectorWorkspacePanel from './ConnectorWorkspacePanel';

describe('ConnectorWorkspacePanel', () => {
  const credentials = [
    {
      id: 'cred-1',
      connector_key: 'http',
      name: 'Example API',
      auth_type: 'api_key_header',
      config_preview: {
        header_name: 'Authorization',
        header_value: '********oken',
      },
    },
  ];

  const triggers = [
    {
      id: 'trigger-1',
      trigger_type: 'webhook',
      webhook_url: 'http://localhost:8001/api/v1/webhooks/public-id',
      is_active: true,
    },
  ];

  const dispatchExecutions = [
    {
      id: 'exec-pending-1',
      status: 'pending',
      created_at: '2026-05-16T10:00:00Z',
      input_data: {
        trigger: {
          type: 'webhook',
          payload: { lead_id: 'lead-123' },
          headers: { authorization: 'secret-token' },
        },
      },
    },
  ];

  const deadLetterDispatchExecutions = [
    {
      id: 'exec-dead-1',
      status: 'failed',
      created_at: '2026-05-16T10:00:00Z',
      input_data: {
        trigger: { type: 'webhook' },
        dispatch: {
          attempt: 3,
          dead_lettered: true,
          dead_letter_reason: 'max_attempts_exhausted',
        },
      },
    },
  ];

  it('renders credential and webhook management for editors', () => {
    const html = renderToStaticMarkup(
      <ConnectorWorkspacePanel
        canManage
        credentials={credentials}
        triggers={triggers}
        dispatchExecutions={dispatchExecutions}
      />
    );

    expect(html).toContain('Connector workspace');
    expect(html).toContain('Credentials');
    expect(html).toContain('Webhook triggers');
    expect(html).toContain('Dispatch queue');
    expect(html).toContain('Pending');
    expect(html).toContain('Create credential');
    expect(html).toContain('Create webhook');
    expect(html).not.toContain('secret-token');
    expect(html).not.toContain('lead-123');
  });

  it('hides mutation controls for viewers', () => {
    const html = renderToStaticMarkup(
      <ConnectorWorkspacePanel
        canManage={false}
        credentials={credentials}
        triggers={triggers}
      />
    );

    expect(html).toContain('Connector workspace');
    expect(html).not.toContain('Create credential');
    expect(html).not.toContain('Create webhook');
    expect(html).not.toContain('Delete');
  });

  it('passes dispatch retry action for editable dead-letter executions', () => {
    const html = renderToStaticMarkup(
      <ConnectorWorkspacePanel
        canManage
        credentials={credentials}
        triggers={triggers}
        dispatchExecutions={deadLetterDispatchExecutions}
        onRetryDispatchExecution={() => {}}
      />
    );

    expect(html).toContain('Dead-letter');
    expect(html).toContain('Retry');
  });
});
