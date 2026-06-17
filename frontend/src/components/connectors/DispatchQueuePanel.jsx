import { useMemo, useState } from 'react';
import { Activity, Clock3, RefreshCw, RotateCcw, RotateCw } from 'lucide-react';

function isWebhookDispatchExecution(execution) {
  return execution?.input_data?.trigger?.type === 'webhook';
}

function compactExecutionId(id = '') {
  if (!id) return 'Unknown execution';
  if (id.length <= 18) return id;
  return `${id.slice(0, 8)}...${id.slice(-4)}`;
}

function formatDateTime(value) {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('en', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function getAttempt(execution) {
  const attempt = Number(execution?.input_data?.dispatch?.attempt || 1);
  return Number.isFinite(attempt) && attempt > 0 ? attempt : 1;
}

export function getDispatchState(execution) {
  const status = execution?.status || 'unknown';
  const dispatch = execution?.input_data?.dispatch || {};
  const attempt = getAttempt(execution);

  if (dispatch.dead_lettered) return 'Dead-letter';
  if (status === 'running') return 'Dispatching';
  if (status === 'pending' && dispatch.next_attempt_at) return 'Deferred retry';
  if (status === 'pending' && attempt > 1) return 'Retry pending';
  if (status === 'pending') return 'Pending';
  if (status === 'completed') return 'Completed';
  if (status === 'failed') return 'Failed';
  if (status === 'cancelled') return 'Cancelled';
  return status.charAt(0).toUpperCase() + status.slice(1);
}

function getStateClasses(state) {
  if (state === 'Dead-letter' || state === 'Failed') {
    return 'border-red-200 bg-red-50 text-red-700';
  }
  if (state === 'Completed') {
    return 'border-emerald-200 bg-emerald-50 text-emerald-700';
  }
  if (state === 'Deferred retry' || state === 'Retry pending') {
    return 'border-amber-200 bg-amber-50 text-amber-700';
  }
  if (state === 'Dispatching') {
    return 'border-blue-200 bg-blue-50 text-blue-700';
  }
  return 'border-gray-200 bg-gray-50 text-gray-700';
}

const DISPATCH_QUEUE_FILTERS = [
  { key: 'all', label: 'All' },
  { key: 'active', label: 'Active' },
  { key: 'deferred', label: 'Deferred' },
  { key: 'dead_letter', label: 'Dead-letter' },
  { key: 'completed', label: 'Completed' },
];

export function filterDispatchExecutions(executions = [], filter = 'all') {
  const webhookExecutions = executions.filter(isWebhookDispatchExecution);

  if (filter === 'all') {
    return webhookExecutions;
  }

  return webhookExecutions.filter((execution) => {
    const state = getDispatchState(execution);

    if (filter === 'active') {
      return state === 'Pending' || state === 'Dispatching' || state === 'Retry pending';
    }
    if (filter === 'deferred') {
      return state === 'Deferred retry';
    }
    if (filter === 'dead_letter') {
      return state === 'Dead-letter';
    }
    if (filter === 'completed') {
      return state === 'Completed' || state === 'Failed' || state === 'Cancelled';
    }

    return true;
  });
}

export default function DispatchQueuePanel({
  executions = [],
  canManage = false,
  loading = false,
  error = '',
  onRefresh,
  onRetry,
  retryingExecutionId = '',
}) {
  const [activeFilter, setActiveFilter] = useState('all');
  const webhookExecutions = useMemo(
    () => filterDispatchExecutions(executions, activeFilter),
    [activeFilter, executions]
  );

  return (
    <section className="bg-white border border-gray-200 rounded-md">
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Activity className="h-4 w-4 text-blue-600" />
          <h2 className="text-sm font-semibold text-gray-900">Dispatch queue</h2>
        </div>
        {onRefresh && (
          <button
            type="button"
            onClick={onRefresh}
            className="inline-flex items-center gap-1.5 rounded-md border border-gray-200 px-2.5 py-1.5 text-xs font-medium text-gray-600 hover:bg-gray-50"
            title="Refresh dispatch queue"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            Refresh
          </button>
        )}
      </div>

      <div className="px-4 py-3 border-b border-gray-100">
        <div className="flex flex-wrap items-center gap-2">
          {DISPATCH_QUEUE_FILTERS.map((filter) => {
            const selected = activeFilter === filter.key;
            return (
              <button
                key={filter.key}
                type="button"
                onClick={() => setActiveFilter(filter.key)}
                className={`rounded-md border px-2.5 py-1.5 text-xs font-medium ${
                  selected
                    ? 'border-blue-200 bg-blue-50 text-blue-700'
                    : 'border-gray-200 bg-white text-gray-600 hover:bg-gray-50'
                }`}
              >
                {filter.label}
              </button>
            );
          })}
        </div>
      </div>

      {error && (
        <div className="mx-4 mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      )}

      <div className="p-4 space-y-2">
        {loading && <p className="text-sm text-gray-500">Loading dispatch queue...</p>}
        {!loading && webhookExecutions.length === 0 && (
          <p className="text-sm text-gray-500">
            {activeFilter === 'all' ? 'No webhook dispatches yet.' : 'No matching webhook dispatches.'}
          </p>
        )}
        {!loading && webhookExecutions.map((execution) => {
          const state = getDispatchState(execution);
          const dispatch = execution.input_data?.dispatch || {};
          const nextAttempt = formatDateTime(dispatch.next_attempt_at);
          const createdAt = formatDateTime(execution.created_at);
          const canRetry = canManage && state === 'Dead-letter' && onRetry;
          const retrying = retryingExecutionId === execution.id;

          return (
            <div
              key={execution.id}
              className="rounded-md border border-gray-200 p-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-mono text-xs font-medium text-gray-900 break-all">
                    {compactExecutionId(execution.id)}
                  </p>
                  <p className="mt-1 flex items-center gap-1 text-xs text-gray-500">
                    <RotateCw className="h-3 w-3" />
                    Attempt {getAttempt(execution)}
                  </p>
                </div>
                <span className={`shrink-0 rounded-full border px-2 py-0.5 text-xs font-medium ${getStateClasses(state)}`}>
                  {state}
                </span>
              </div>

              <div className="mt-2 space-y-1 text-xs text-gray-500">
                {nextAttempt && (
                  <p className="flex items-center gap-1">
                    <Clock3 className="h-3 w-3" />
                    Next attempt {nextAttempt}
                  </p>
                )}
                {createdAt && <p>Created {createdAt}</p>}
              </div>

              {canRetry && (
                <div className="mt-3 flex justify-end">
                  <button
                    type="button"
                    onClick={() => onRetry?.(execution.id)}
                    disabled={retrying}
                    className="inline-flex items-center gap-1.5 rounded-md border border-red-200 px-2.5 py-1.5 text-xs font-medium text-red-700 hover:bg-red-50 disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <RotateCcw className="h-3.5 w-3.5" />
                    {retrying ? 'Retrying...' : 'Retry'}
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
