import {
  Activity,
  CalendarClock,
  Clock3,
  DatabaseZap,
  History,
  ShieldCheck,
  TimerReset,
} from 'lucide-react';

function formatDateTime(value) {
  if (!value) return '';
  return new Date(value).toLocaleString();
}

function readinessLabel(diagnostics) {
  if (diagnostics.tenant_due_now) return 'Ready now';
  if (diagnostics.tenant_skip_reason === 'backoff') return 'Backoff';
  if (diagnostics.tenant_skip_reason === 'tenant_disabled') return 'Tenant disabled';
  if (diagnostics.tenant_skip_reason === 'interval') return 'Waiting';
  return 'Not due';
}

function readinessTone(label) {
  if (label === 'Ready now') return 'border-green-200 bg-green-50 text-green-700';
  if (label === 'Backoff') return 'border-red-200 bg-red-50 text-red-700';
  if (label === 'Waiting') return 'border-blue-200 bg-blue-50 text-blue-700';
  return 'border-gray-200 bg-gray-50 text-gray-700';
}

function statusTone(status) {
  if (status === 'completed') return 'border-green-200 bg-green-50 text-green-700';
  if (status === 'failed') return 'border-red-200 bg-red-50 text-red-700';
  return 'border-gray-200 bg-white text-gray-600';
}

export default function DispatchSchedulerDiagnosticsPanel({
  diagnostics,
  userRole = 'viewer',
}) {
  if (userRole !== 'owner' || !diagnostics) return null;

  const tenantConfig = diagnostics.tenant_config || {
    enabled: false,
    interval_minutes: 15,
    max_plans_per_run: 10,
  };
  const latestRun = diagnostics.latest_scheduled_run;
  const readiness = readinessLabel(diagnostics);

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-gray-500" />
            <h2 className="text-base font-semibold text-gray-900">Scheduler diagnostics</h2>
            <span className="rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-xs font-medium text-gray-600">
              read-only
            </span>
          </div>
          <p className="mt-1 text-sm text-gray-600">
            {`Generated ${formatDateTime(diagnostics.generated_at)}`}
          </p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-4">
        <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-3">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-gray-500" />
            <p className="text-sm font-semibold text-gray-900">Global scheduler</p>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
              diagnostics.scheduler_enabled
                ? 'border-green-200 bg-green-50 text-green-700'
                : 'border-gray-200 bg-white text-gray-600'
            }`}
            >
              {diagnostics.scheduler_enabled ? 'enabled' : 'disabled'}
            </span>
            <span className="rounded-full bg-white px-2 py-0.5 text-xs text-gray-600">
              {`Every ${diagnostics.scheduler_interval_seconds}s`}
            </span>
            <span className="rounded-full bg-white px-2 py-0.5 text-xs text-gray-600">
              {`Tenant limit ${diagnostics.scheduler_tenant_limit}`}
            </span>
          </div>
        </div>

        <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-3">
          <div className="flex items-center gap-2">
            <CalendarClock className="h-4 w-4 text-gray-500" />
            <p className="text-sm font-semibold text-gray-900">Tenant schedule</p>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
              tenantConfig.enabled
                ? 'border-green-200 bg-green-50 text-green-700'
                : 'border-gray-200 bg-white text-gray-600'
            }`}
            >
              {tenantConfig.enabled ? 'enabled' : 'disabled'}
            </span>
            <span className="rounded-full bg-white px-2 py-0.5 text-xs text-gray-600">
              {`Every ${tenantConfig.interval_minutes} min`}
            </span>
            <span className="rounded-full bg-white px-2 py-0.5 text-xs text-gray-600">
              {`Max ${tenantConfig.max_plans_per_run} plans`}
            </span>
          </div>
        </div>

        <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-3">
          <div className="flex items-center gap-2">
            <DatabaseZap className="h-4 w-4 text-gray-500" />
            <p className="text-sm font-semibold text-gray-900">Approved backlog</p>
          </div>
          <p className="mt-2 text-2xl font-semibold text-gray-900">
            {diagnostics.approved_plan_count || 0}
          </p>
        </div>

        <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-3">
          <div className="flex items-center gap-2">
            <TimerReset className="h-4 w-4 text-gray-500" />
            <p className="text-sm font-semibold text-gray-900">Tenant readiness</p>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${readinessTone(readiness)}`}>
              {readiness}
            </span>
            {diagnostics.next_run_at && (
              <span className="rounded-full bg-white px-2 py-0.5 text-xs text-gray-600">
                {`Next ${formatDateTime(diagnostics.next_run_at)}`}
              </span>
            )}
            {diagnostics.backoff_until && (
              <span className="rounded-full bg-white px-2 py-0.5 text-xs text-gray-600">
                {`Backoff until ${formatDateTime(diagnostics.backoff_until)}`}
              </span>
            )}
          </div>
        </div>
      </div>

      <div className="mt-5 border-t border-gray-100 pt-4">
        <div className="flex items-center gap-2">
          <History className="h-4 w-4 text-gray-500" />
          <h3 className="text-sm font-semibold text-gray-900">Latest scheduled run</h3>
        </div>

        {!latestRun ? (
          <div className="mt-2 rounded-md bg-gray-50 px-3 py-2 text-sm text-gray-500">
            No scheduled worker runs recorded yet.
          </div>
        ) : (
          <div className="mt-2 rounded-md border border-gray-200 bg-gray-50 px-3 py-3">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-gray-600">
                    {latestRun.trigger_type}
                  </span>
                  <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${statusTone(latestRun.status)}`}>
                    {latestRun.status}
                  </span>
                  <span className="inline-flex items-center gap-1 text-xs text-gray-500">
                    <Clock3 className="h-3 w-3" />
                    {formatDateTime(latestRun.created_at)}
                  </span>
                </div>
                {latestRun.error_message && (
                  <p className="mt-2 text-xs text-red-600">{latestRun.error_message}</p>
                )}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {['claimed', 'executed', 'blocked', 'failed'].map((key) => (
                  <span key={key} className="rounded-full bg-white px-2 py-0.5 text-xs text-gray-600">
                    {`${key}: ${latestRun[key] || 0}`}
                  </span>
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

    </section>
  );
}
