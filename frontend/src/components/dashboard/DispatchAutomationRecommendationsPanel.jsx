import {
  Bot,
  CheckCircle2,
  ClipboardList,
  Clock3,
  Lock,
  PlusCircle,
  PlayCircle,
  Settings2,
  Sparkles,
  XCircle,
} from 'lucide-react';

const priorityClasses = {
  critical: 'bg-red-50 text-red-700 border-red-200',
  warning: 'bg-amber-50 text-amber-700 border-amber-200',
  info: 'bg-blue-50 text-blue-700 border-blue-200',
};

const statusClasses = {
  pending_approval: 'bg-amber-50 text-amber-700 border-amber-200',
  approved: 'bg-blue-50 text-blue-700 border-blue-200',
  executing: 'bg-purple-50 text-purple-700 border-purple-200',
  executed: 'bg-green-50 text-green-700 border-green-200',
  blocked: 'bg-gray-50 text-gray-700 border-gray-200',
  failed: 'bg-red-50 text-red-700 border-red-200',
  rejected: 'bg-gray-50 text-gray-600 border-gray-200',
};

const hiddenResultKeys = [
  'payload',
  'headers',
  'header',
  'body',
  'input',
  'input_data',
  'workflow_definition',
  'definition',
  'config',
  'credential',
  'secret',
  'token',
  'note',
  'email',
  'name',
];

function isHiddenResultKey(key) {
  const normalized = String(key || '').toLowerCase();
  return hiddenResultKeys.some((needle) => normalized.includes(needle));
}

function safeResultEntries(result = {}) {
  return Object.entries(result || {})
    .filter(([key, value]) => !isHiddenResultKey(key) && value !== null && value !== undefined)
    .map(([key, value]) => {
      if (Array.isArray(value)) {
        return [key, value.length];
      }
      if (typeof value === 'object') {
        return [key, Object.keys(value).length];
      }
      return [key, value];
    });
}

function planTimestamp(plan) {
  return plan.executed_at || plan.rejected_at || plan.approved_at || plan.created_at;
}

export default function DispatchAutomationRecommendationsPanel({
  recommendations,
  plans,
  userRole = 'viewer',
  busyAction = '',
  workerRunning = false,
  workerResult = null,
  workerConfig = null,
  workerRuns = null,
  onCreatePlan,
  onApprovePlan,
  onRejectPlan,
  onRunWorker,
  onUpdateWorkerConfig,
}) {
  const items = recommendations?.recommendations || [];
  const planItems = plans?.items || [];
  const runItems = workerRuns?.items || [];
  const scheduleConfig = workerConfig || {
    enabled: false,
    interval_minutes: 15,
    max_plans_per_run: 10,
  };
  const summary = `${recommendations?.recommendation_count || 0} recommendations · ${recommendations?.automation_ready_count || 0} ready · dry-run`;
  const canCreatePlan = userRole === 'owner' || userRole === 'editor';
  const canApprovePlan = userRole === 'owner';
  const canRunWorker = userRole === 'owner';
  const approvedPlanCount = planItems.filter((plan) => plan.status === 'approved').length;
  const activePlanStatuses = new Set(['pending_approval', 'approved', 'executing']);

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold text-gray-900">Automation recommendations</h2>
            <span className="rounded-full border border-green-200 bg-green-50 px-2 py-0.5 text-xs font-medium text-green-700">
              dry-run
            </span>
          </div>
          <p className="mt-1 text-sm text-gray-600">{summary}</p>
        </div>
      </div>

      <div className="mt-4 space-y-2">
        {items.length === 0 && (
          <div className="rounded-md bg-gray-50 px-3 py-2 text-sm text-gray-500">
            No automation recommendations for the current dispatch window.
          </div>
        )}

        {items.map((item) => {
          const priorityClass = priorityClasses[item.priority] || priorityClasses.info;
          return (
            <div key={item.code} className="rounded-md border border-gray-200 bg-gray-50 px-3 py-3">
              <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-gray-900">{item.title}</p>
                    <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${priorityClass}`}>
                      {item.priority}
                    </span>
                    <span className="inline-flex items-center gap-1 rounded-full bg-white px-2 py-0.5 text-xs font-medium text-gray-600">
                      <Bot className="h-3 w-3" />
                      {item.automation_type}
                    </span>
                  </div>
                  <p className="mt-1 text-xs text-gray-600">{item.rationale}</p>
                  <p className="mt-1 text-xs text-gray-700">{item.suggested_action}</p>
                </div>
                <div className="flex shrink-0 flex-col items-start gap-2 sm:items-end">
                  <div className="inline-flex items-center gap-1 text-xs font-medium text-gray-500">
                    <Sparkles className="h-3.5 w-3.5" />
                    {Math.round((item.confidence || 0) * 100)}%
                  </div>
                  {canCreatePlan && (() => {
                    const activePlan = planItems.find(
                      (plan) => plan.recommendation_code === item.code
                        && activePlanStatuses.has(plan.status)
                    );
                    if (activePlan) {
                      return (
                        <span className="rounded-full border border-gray-200 bg-white px-2 py-1 text-xs font-medium text-gray-600">
                          Plan {activePlan.status}
                        </span>
                      );
                    }
                    const actionKey = `create:${item.code}`;
                    return (
                      <button
                        type="button"
                        onClick={() => onCreatePlan?.(item.code)}
                        disabled={busyAction === actionKey}
                        className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-2.5 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:opacity-50"
                      >
                        <PlusCircle className="h-3.5 w-3.5" />
                        {busyAction === actionKey ? 'Creating...' : 'Create plan'}
                      </button>
                    );
                  })()}
                </div>
              </div>

              {item.evidence?.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {item.evidence.map((evidence) => (
                    <span key={evidence} className="rounded-full bg-white px-2 py-0.5 text-xs text-gray-600">
                      {evidence}
                    </span>
                  ))}
                </div>
              )}

              {item.blocked_by?.length > 0 && (
                <div className="mt-3 flex flex-wrap gap-1.5">
                  {item.blocked_by.map((blocker) => (
                    <span
                      key={blocker}
                      className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-xs font-medium text-amber-700"
                    >
                      <Lock className="h-3 w-3" />
                      {blocker}
                    </span>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="mt-6 border-t border-gray-100 pt-4">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
          <div>
            <div className="flex items-center gap-2">
              <ClipboardList className="h-4 w-4 text-gray-500" />
              <h3 className="text-sm font-semibold text-gray-900">Automation plans</h3>
              <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
                {planItems.length}
              </span>
            </div>
            {workerResult && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {['claimed', 'executed', 'blocked', 'failed'].map((key) => (
                  <span key={key} className="rounded-full bg-gray-100 px-2 py-0.5 text-xs text-gray-600">
                    {`${key}: ${workerResult[key] || 0}`}
                  </span>
                ))}
              </div>
            )}
          </div>

          {canRunWorker && (
            <button
              type="button"
              onClick={() => onRunWorker?.()}
              disabled={workerRunning || busyAction === 'worker:run' || approvedPlanCount === 0}
              className="inline-flex items-center gap-1.5 rounded-md border border-blue-200 bg-blue-50 px-3 py-1.5 text-xs font-medium text-blue-700 transition-colors hover:bg-blue-100 disabled:opacity-50"
            >
              <PlayCircle className="h-3.5 w-3.5" />
              {workerRunning || busyAction === 'worker:run' ? 'Running...' : 'Run worker'}
            </button>
          )}
        </div>

        <div className="mt-4 rounded-md border border-gray-200 bg-gray-50 px-3 py-3">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2">
                <Settings2 className="h-4 w-4 text-gray-500" />
                <h3 className="text-sm font-semibold text-gray-900">Worker schedule</h3>
                <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
                  scheduleConfig.enabled
                    ? 'border-green-200 bg-green-50 text-green-700'
                    : 'border-gray-200 bg-white text-gray-600'
                }`}
                >
                  {scheduleConfig.enabled ? 'enabled' : 'disabled'}
                </span>
              </div>
              <div className="mt-2 flex flex-wrap gap-1.5">
                <span className="rounded-full bg-white px-2 py-0.5 text-xs text-gray-600">
                  {`Every ${scheduleConfig.interval_minutes} min`}
                </span>
                <span className="rounded-full bg-white px-2 py-0.5 text-xs text-gray-600">
                  {`Max ${scheduleConfig.max_plans_per_run} plans`}
                </span>
              </div>
            </div>

            {canRunWorker && (
              <button
                type="button"
                onClick={() => onUpdateWorkerConfig?.({
                  ...scheduleConfig,
                  enabled: !scheduleConfig.enabled,
                })}
                disabled={busyAction === 'worker:config'}
                className="inline-flex items-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:opacity-50"
              >
                <Clock3 className="h-3.5 w-3.5" />
                {busyAction === 'worker:config'
                  ? 'Updating...'
                  : scheduleConfig.enabled
                    ? 'Disable schedule'
                    : 'Enable schedule'}
              </button>
            )}
          </div>
        </div>

        <div className="mt-4">
          <div className="flex items-center gap-2">
            <Clock3 className="h-4 w-4 text-gray-500" />
            <h3 className="text-sm font-semibold text-gray-900">Recent worker runs</h3>
            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
              {runItems.length}
            </span>
          </div>
          <div className="mt-2 space-y-2">
            {runItems.length === 0 && (
              <div className="rounded-md bg-gray-50 px-3 py-2 text-sm text-gray-500">
                No automation worker runs recorded yet.
              </div>
            )}

            {runItems.map((run) => (
              <div key={run.id} className="rounded-md border border-gray-200 bg-gray-50 px-3 py-2">
                <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-gray-600">
                        {run.trigger_type}
                      </span>
                      <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
                        run.status === 'completed'
                          ? 'border-green-200 bg-green-50 text-green-700'
                          : 'border-red-200 bg-red-50 text-red-700'
                      }`}
                      >
                        {run.status}
                      </span>
                      <span className="text-xs text-gray-500">
                        {run.created_at ? new Date(run.created_at).toLocaleString() : ''}
                      </span>
                    </div>
                    {run.error_message && (
                      <p className="mt-1 text-xs text-red-600">{run.error_message}</p>
                    )}
                  </div>
                  <div className="flex flex-wrap gap-1.5">
                    {['claimed', 'executed', 'blocked', 'failed'].map((key) => (
                      <span key={key} className="rounded-full bg-white px-2 py-0.5 text-xs text-gray-600">
                        {`${key}: ${run[key] || 0}`}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-3 space-y-2">
          {planItems.length === 0 && (
            <div className="rounded-md bg-gray-50 px-3 py-2 text-sm text-gray-500">
              No automation plans created yet.
            </div>
          )}

          {planItems.map((plan) => {
            const statusClass = statusClasses[plan.status] || statusClasses.blocked;
            const resultEntries = safeResultEntries(plan.execution_result);
            return (
              <div key={plan.id} className="rounded-md border border-gray-200 bg-gray-50 px-3 py-3">
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <div className="flex flex-wrap items-center gap-2">
                      <p className="text-sm font-semibold text-gray-900">{plan.title}</p>
                      <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${statusClass}`}>
                        {plan.status}
                      </span>
                      <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-gray-600">
                        {plan.automation_type}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-gray-500">
                      {plan.recommendation_code}
                      {planTimestamp(plan) ? ` · ${new Date(planTimestamp(plan)).toLocaleString()}` : ''}
                    </p>
                    {resultEntries.length > 0 && (
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        {resultEntries.map(([key, value]) => (
                          <span key={key} className="rounded-full bg-white px-2 py-0.5 text-xs text-gray-600">
                            {key}: {String(value)}
                          </span>
                        ))}
                      </div>
                    )}
                    {plan.execution_error && (
                      <p className="mt-2 text-xs text-red-600">{plan.execution_error}</p>
                    )}
                  </div>

                  {canApprovePlan && plan.status === 'pending_approval' && (
                    <div className="flex shrink-0 flex-wrap gap-2">
                      <button
                        type="button"
                        onClick={() => onApprovePlan?.(plan.id)}
                        disabled={busyAction === `approve:${plan.id}`}
                        className="inline-flex items-center gap-1.5 rounded-md border border-green-200 bg-green-50 px-2.5 py-1.5 text-xs font-medium text-green-700 transition-colors hover:bg-green-100 disabled:opacity-50"
                      >
                        <CheckCircle2 className="h-3.5 w-3.5" />
                        {busyAction === `approve:${plan.id}` ? 'Approving...' : 'Approve'}
                      </button>
                      <button
                        type="button"
                        onClick={() => onRejectPlan?.(plan.id)}
                        disabled={busyAction === `reject:${plan.id}`}
                        className="inline-flex items-center gap-1.5 rounded-md border border-red-200 bg-red-50 px-2.5 py-1.5 text-xs font-medium text-red-700 transition-colors hover:bg-red-100 disabled:opacity-50"
                      >
                        <XCircle className="h-3.5 w-3.5" />
                        {busyAction === `reject:${plan.id}` ? 'Rejecting...' : 'Reject'}
                      </button>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
}
