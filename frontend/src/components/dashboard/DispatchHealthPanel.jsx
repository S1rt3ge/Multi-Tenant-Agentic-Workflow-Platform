import {
  AlertTriangle,
  Clock3,
  Gauge,
  Inbox,
  PauseCircle,
  RotateCcw,
  ShieldCheck,
} from 'lucide-react';

const severityClasses = {
  critical: 'border-red-200 bg-red-50 text-red-700',
  warning: 'border-amber-200 bg-amber-50 text-amber-700',
  info: 'border-blue-200 bg-blue-50 text-blue-700',
};

export default function DispatchHealthPanel({ health }) {
  if (!health) return null;

  const metrics = [
    {
      label: 'Paused workflows',
      value: health.paused_workflows,
      icon: PauseCircle,
      tone: health.paused_workflows > 0 ? 'text-amber-600 bg-amber-50' : 'text-gray-500 bg-gray-50',
    },
    {
      label: 'Throttled triggers',
      value: health.throttled_triggers,
      icon: Gauge,
      tone: health.throttled_triggers > 0 ? 'text-amber-600 bg-amber-50' : 'text-gray-500 bg-gray-50',
    },
    {
      label: 'Pending dispatches',
      value: health.pending_dispatches,
      icon: Inbox,
      tone: 'text-blue-600 bg-blue-50',
    },
    {
      label: 'Deferred retries',
      value: health.deferred_retries,
      icon: Clock3,
      tone: health.deferred_retries > 0 ? 'text-blue-600 bg-blue-50' : 'text-gray-500 bg-gray-50',
    },
    {
      label: 'Dead-lettered',
      value: health.dead_lettered_executions,
      icon: AlertTriangle,
      tone: health.dead_lettered_executions > 0 ? 'text-red-600 bg-red-50' : 'text-gray-500 bg-gray-50',
    },
    {
      label: 'Manual retries',
      value: health.manual_retries,
      icon: RotateCcw,
      tone: 'text-emerald-600 bg-emerald-50',
    },
  ];

  return (
    <section className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">Dispatch health</h3>
          <p className="mt-1 text-xs text-gray-500">Webhook queue controls and retry pressure</p>
        </div>
        <div className="rounded-lg bg-emerald-50 p-2 text-emerald-600">
          <ShieldCheck className="h-4 w-4" />
        </div>
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-6 gap-3">
        {metrics.map((metric) => {
          const Icon = metric.icon;
          return (
            <div key={metric.label} className="rounded-lg border border-gray-100 px-3 py-3">
              <div className={`mb-2 inline-flex rounded-md p-1.5 ${metric.tone}`}>
                <Icon className="h-3.5 w-3.5" />
              </div>
              <p className="text-xl font-semibold text-gray-900">{metric.value}</p>
              <p className="mt-1 text-xs text-gray-500">{metric.label}</p>
            </div>
          );
        })}
      </div>

      <div className="mt-4 space-y-2">
        {health.alerts.length === 0 ? (
          <div className="rounded-lg border border-emerald-100 bg-emerald-50 px-3 py-2 text-xs text-emerald-700">
            No active dispatch alerts
          </div>
        ) : (
          health.alerts.map((alert) => (
            <div
              key={alert.code}
              className={`rounded-lg border px-3 py-2 text-xs ${
                severityClasses[alert.severity] || severityClasses.info
              }`}
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-medium">{alert.title}</p>
                  <p className="mt-0.5 opacity-90">{alert.message}</p>
                </div>
                <span className="shrink-0 font-semibold">{alert.count}</span>
              </div>
            </div>
          ))
        )}
      </div>
    </section>
  );
}
