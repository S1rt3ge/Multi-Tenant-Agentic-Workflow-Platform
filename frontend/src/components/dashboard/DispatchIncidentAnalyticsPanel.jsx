import { Activity, AlertTriangle, CheckCircle2, Clock3 } from 'lucide-react';

function minutesLabel(value) {
  if (value === null || value === undefined) return 'N/A';
  return `${value}m`;
}

function metricCards(analytics) {
  return [
    {
      label: 'Total incidents',
      value: analytics?.total_incidents ?? 0,
      icon: Activity,
      tone: 'text-gray-700 bg-gray-50 border-gray-200',
    },
    {
      label: 'Resolved',
      value: analytics?.resolved_incidents ?? 0,
      icon: CheckCircle2,
      tone: 'text-green-700 bg-green-50 border-green-200',
    },
    {
      label: 'SLA breaches',
      value: analytics?.sla_breaches ?? 0,
      icon: AlertTriangle,
      tone: 'text-red-700 bg-red-50 border-red-200',
    },
    {
      label: 'Avg resolution',
      value: minutesLabel(analytics?.avg_resolution_minutes),
      icon: Clock3,
      tone: 'text-blue-700 bg-blue-50 border-blue-200',
    },
  ];
}

export default function DispatchIncidentAnalyticsPanel({ analytics }) {
  const trends = analytics?.trends || [];
  const bySeverity = analytics?.by_severity || [];
  const maxDaily = Math.max(1, ...trends.map((item) => item.acknowledged || 0));
  const visibleTrends = trends.slice(-7);
  const summary = `${analytics?.window_days || 30}d window · ${analytics?.sla_minutes || 60}m SLA · ${analytics?.sla_breach_rate ?? 0}% breach rate`;

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-gray-900">Incident analytics</h2>
          <p className="mt-1 text-sm text-gray-600">{summary}</p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {metricCards(analytics).map((card) => {
          const Icon = card.icon;
          return (
            <div key={card.label} className={`rounded-md border px-3 py-2 ${card.tone}`}>
              <div className="flex items-center justify-between gap-2">
                <p className="text-xs font-medium">{card.label}</p>
                <Icon className="h-3.5 w-3.5" />
              </div>
              <p className="mt-1 text-lg font-semibold">{card.value}</p>
            </div>
          );
        })}
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div>
          <p className="text-xs font-semibold text-gray-900">Daily trend</p>
          <div className="mt-2 space-y-2">
            {visibleTrends.length === 0 && (
              <p className="text-sm text-gray-500">No incident data yet</p>
            )}
            {visibleTrends.map((item) => {
              const width = `${Math.max(6, ((item.acknowledged || 0) / maxDaily) * 100)}%`;
              return (
                <div key={item.day} className="rounded-md bg-gray-50 px-3 py-2 text-xs">
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium text-gray-900">{item.day}</span>
                    <span className="text-gray-500">
                      {item.resolved} resolved · {item.open} open · {item.sla_breaches} SLA
                    </span>
                  </div>
                  <div className="mt-2 h-1.5 rounded-full bg-gray-200">
                    <div className="h-1.5 rounded-full bg-blue-600" style={{ width }} />
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        <div>
          <p className="text-xs font-semibold text-gray-900">Severity breakdown</p>
          <div className="mt-2 space-y-2">
            {bySeverity.length === 0 && (
              <p className="text-sm text-gray-500">No incident severity data yet</p>
            )}
            {bySeverity.map((item) => (
              <div key={item.severity} className="rounded-md bg-gray-50 px-3 py-2 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium text-gray-900">{item.severity}</p>
                  <span className="rounded-full bg-white px-2 py-0.5 font-medium text-gray-600">
                    {minutesLabel(item.avg_resolution_minutes)}
                  </span>
                </div>
                <p className="mt-1 text-gray-600">
                  {item.total_incidents} total · {item.resolved_incidents} resolved · {item.open_incidents} open · {item.sla_breaches} SLA breaches
                </p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
