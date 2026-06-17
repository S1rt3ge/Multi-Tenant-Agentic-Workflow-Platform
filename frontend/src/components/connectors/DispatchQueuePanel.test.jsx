import { renderToStaticMarkup } from 'react-dom/server';
import { describe, expect, it } from 'vitest';

import DispatchQueuePanel, { filterDispatchExecutions } from './DispatchQueuePanel';

describe('DispatchQueuePanel', () => {
  const executions = [
    {
      id: 'exec-pending-1',
      status: 'pending',
      created_at: '2026-05-16T10:00:00Z',
      input_data: {
        trigger: {
          type: 'webhook',
          payload: { lead_id: 'lead-123' },
          headers: { 'x-webhook-secret': 'secret-webhook-header' },
        },
      },
    },
    {
      id: 'exec-retry-2',
      status: 'pending',
      created_at: '2026-05-16T10:01:00Z',
      input_data: {
        trigger: { type: 'webhook' },
        dispatch: {
          attempt: 2,
          next_attempt_at: '2026-05-16T10:05:00Z',
        },
      },
    },
    {
      id: 'exec-dead-3',
      status: 'failed',
      created_at: '2026-05-16T10:02:00Z',
      input_data: {
        trigger: { type: 'webhook' },
        dispatch: {
          attempt: 3,
          dead_lettered: true,
          dead_letter_reason: 'max_attempts_exhausted',
        },
      },
    },
    {
      id: 'exec-manual-4',
      status: 'pending',
      created_at: '2026-05-16T10:03:00Z',
      input_data: {
        trigger: { type: 'manual' },
      },
    },
    {
      id: 'exec-completed-5',
      status: 'completed',
      created_at: '2026-05-16T10:04:00Z',
      input_data: {
        trigger: { type: 'webhook' },
      },
    },
  ];

  it('filters webhook dispatch executions by operational state', () => {
    expect(filterDispatchExecutions(executions, 'dead_letter').map((item) => item.id)).toEqual([
      'exec-dead-3',
    ]);
    expect(filterDispatchExecutions(executions, 'deferred').map((item) => item.id)).toEqual([
      'exec-retry-2',
    ]);
    expect(filterDispatchExecutions(executions, 'active').map((item) => item.id)).toEqual([
      'exec-pending-1',
    ]);
    expect(filterDispatchExecutions(executions, 'completed').map((item) => item.id)).toEqual([
      'exec-completed-5',
    ]);
    expect(filterDispatchExecutions(executions, 'all').map((item) => item.id)).not.toContain(
      'exec-manual-4'
    );
  });

  it('renders webhook dispatch states and retry metadata', () => {
    const html = renderToStaticMarkup(<DispatchQueuePanel executions={executions} />);

    expect(html).toContain('Dispatch queue');
    expect(html).toContain('All');
    expect(html).toContain('Active');
    expect(html).toContain('Deferred');
    expect(html).toContain('Pending');
    expect(html).toContain('Deferred retry');
    expect(html).toContain('Dead-letter');
    expect(html).toContain('Completed');
    expect(html).toContain('Attempt 2');
    expect(html).toContain('Next attempt');
    expect(html).toContain('exec-pending-1');
    expect(html).not.toContain('exec-manual-4');
  });

  it('does not render raw webhook payloads or headers', () => {
    const html = renderToStaticMarkup(<DispatchQueuePanel executions={executions} />);

    expect(html).not.toContain('lead-123');
    expect(html).not.toContain('secret-webhook-header');
    expect(html).not.toContain('x-webhook-secret');
  });

  it('renders retry action only for editors on dead-letter executions', () => {
    const editorHtml = renderToStaticMarkup(
      <DispatchQueuePanel
        canManage
        executions={executions}
        onRetry={() => {}}
      />
    );
    const viewerHtml = renderToStaticMarkup(
      <DispatchQueuePanel
        canManage={false}
        executions={executions}
        onRetry={() => {}}
      />
    );

    expect(editorHtml).toContain('Retry');
    expect((editorHtml.match(/Retry/g) || []).length).toBe(1);
    expect(viewerHtml).not.toContain('Retry');
  });
});
