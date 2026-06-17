import {
  Activity,
  Building2,
  CalendarClock,
  Clock3,
  DatabaseZap,
  ListChecks,
  ShieldCheck,
  TimerReset,
} from 'lucide-react';

function formatDateTime(value) {
  if (!value) return '';
  return new Date(value).toLocaleString();
}

function readinessLabel(summary) {
  if (summary.due_now) return 'Ready now';
  if (summary.skip_reason === 'backoff') return 'Backoff';
  if (summary.skip_reason === 'tenant_disabled') return 'Tenant disabled';
  if (summary.skip_reason === 'interval') return 'Waiting';
  return 'Not due';
}

function readinessTone(label) {
  if (label === 'Ready now') return 'border-green-200 bg-green-50 text-green-700';
  if (label === 'Backoff') return 'border-red-200 bg-red-50 text-red-700';
  if (label === 'Waiting') return 'border-blue-200 bg-blue-50 text-blue-700';
  return 'border-gray-200 bg-white text-gray-600';
}

function statusTone(status) {
  if (status === 'completed') return 'border-green-200 bg-green-50 text-green-700';
  if (status === 'failed') return 'border-red-200 bg-red-50 text-red-700';
  if (status) return 'border-gray-200 bg-white text-gray-600';
  return 'border-gray-200 bg-white text-gray-500';
}

function CountTile({ icon: Icon, label, value }) {
  return (
    <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-3">
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 text-gray-500" />
        <p className="text-sm font-semibold text-gray-900">{label}</p>
      </div>
      <p className="mt-2 text-2xl font-semibold text-gray-900">{value || 0}</p>
    </div>
  );
}

export default function DispatchSchedulerFleetPanel({
  fleet,
  userRole = 'viewer',
}) {
  if (userRole !== 'platform_admin' || !fleet) return null;

  const tenantRows = fleet.tenants || [];

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-gray-500" />
            <h2 className="text-base font-semibold text-gray-900">Scheduler fleet</h2>
            <span className="rounded-full border border-blue-200 bg-blue-50 px-2 py-0.5 text-xs font-medium text-blue-700">
              platform-admin
            </span>
            <span className="rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-xs font-medium text-gray-600">
              read-only
            </span>
          </div>
          <p className="mt-1 text-sm text-gray-600">
            {`Generated ${formatDateTime(fleet.generated_at)}`}
          </p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-md border border-gray-200 bg-gray-50 px-3 py-3">
          <div className="flex items-center gap-2">
            <Activity className="h-4 w-4 text-gray-500" />
            <p className="text-sm font-semibold text-gray-900">Global scheduler</p>
          </div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
              fleet.scheduler_enabled
                ? 'border-green-200 bg-green-50 text-green-700'
                : 'border-gray-200 bg-white text-gray-600'
            }`}
            >
              {fleet.scheduler_enabled ? 'enabled' : 'disabled'}
            </span>
            <span className="rounded-full bg-white px-2 py-0.5 text-xs text-gray-600">
              {`Every ${fleet.scheduler_interval_seconds}s`}
            </span>
            <span className="rounded-full bg-white px-2 py-0.5 text-xs text-gray-600">
              {`Tenant limit ${fleet.scheduler_tenant_limit}`}
            </span>
          </div>
        </div>

        <CountTile icon={Building2} label="Total tenants" value={fleet.total_tenants} />
        <CountTile icon={CalendarClock} label="Enabled" value={fleet.enabled_tenants} />
        <CountTile icon={DatabaseZap} label="Approved backlog" value={fleet.approved_plan_backlog} />
      </div>

      <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        <CountTile icon={TimerReset} label="Due now" value={fleet.due_tenants} />
        <CountTile icon={Clock3} label="Waiting" value={fleet.interval_waiting_tenants} />
        <CountTile icon={Activity} label="Backoff" value={fleet.backoff_tenants} />
        <CountTile icon={ListChecks} label="Disabled" value={fleet.disabled_tenants} />
      </div>

      <div className="mt-5 border-t border-gray-100 pt-4">
        <div className="flex items-center gap-2">
          <ListChecks className="h-4 w-4 text-gray-500" />
          <h3 className="text-sm font-semibold text-gray-900">Tenant readiness</h3>
          <span className="rounded-full bg-gray-100 px-2 py-0.5 text-xs font-medium text-gray-600">
            {tenantRows.length}
          </span>
        </div>

        {tenantRows.length === 0 ? (
          <div className="mt-2 rounded-md bg-gray-50 px-3 py-2 text-sm text-gray-500">
            No tenant readiness rows in this snapshot.
          </div>
        ) : (
          <div className="mt-2 space-y-2">
            {tenantRows.map((summary) => {
              const readiness = readinessLabel(summary);
              return (
                <div key={summary.tenant_id} className="rounded-md border border-gray-200 bg-gray-50 px-3 py-3">
                  <div className="flex flex-col gap-2 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-full bg-white px-2 py-0.5 text-xs font-medium text-gray-600">
                          {summary.tenant_id}
                        </span>
                        <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${readinessTone(readiness)}`}>
                          {readiness}
                        </span>
                        <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${
                          summary.enabled
                            ? 'border-green-200 bg-green-50 text-green-700'
                            : 'border-gray-200 bg-white text-gray-600'
                        }`}
                        >
                          {summary.enabled ? 'enabled' : 'disabled'}
                        </span>
                      </div>
                      <div className="mt-2 flex flex-wrap gap-1.5">
                        <span className="rounded-full bg-white px-2 py-0.5 text-xs text-gray-600">
                          {`Approved ${summary.approved_plan_count || 0}`}
                        </span>
                        <span className="rounded-full bg-white px-2 py-0.5 text-xs text-gray-600">
                          {`Max ${summary.max_plans_per_run || 0} plans`}
                        </span>
                        {summary.latest_scheduled_status && (
                          <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${statusTone(summary.latest_scheduled_status)}`}>
                            {`Latest ${summary.latest_scheduled_status}`}
                          </span>
                        )}
                      </div>
                    </div>

                    <div className="flex shrink-0 flex-wrap gap-1.5">
                      {summary.next_run_at && (
                        <span className="rounded-full bg-white px-2 py-0.5 text-xs text-gray-600">
                          {`Next ${formatDateTime(summary.next_run_at)}`}
                        </span>
                      )}
                      {summary.backoff_until && (
                        <span className="rounded-full bg-white px-2 py-0.5 text-xs text-gray-600">
                          {`Backoff until ${formatDateTime(summary.backoff_until)}`}
                        </span>
                      )}
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </section>
  );
}
