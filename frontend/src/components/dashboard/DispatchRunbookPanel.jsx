import { CheckCircle2, Download, ShieldCheck } from 'lucide-react';

const severityClasses = {
  critical: 'bg-red-50 text-red-700 border-red-200',
  warning: 'bg-amber-50 text-amber-700 border-amber-200',
  info: 'bg-blue-50 text-blue-700 border-blue-200',
};

export default function DispatchRunbookPanel({
  runbook,
  onExport,
  onAcknowledge,
  onResolve,
  exporting,
  acknowledging,
  resolving,
}) {
  const actions = runbook?.recommended_actions || [];
  const deliveries = runbook?.recent_deliveries || [];
  const severity = runbook?.severity || 'info';
  const acknowledgement = runbook?.acknowledgement || null;
  const incidentHistory = runbook?.incident_history || [];
  const canAcknowledge = runbook && severity !== 'info' && !acknowledgement;

  return (
    <section className="rounded-lg border border-gray-200 bg-white p-5">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold text-gray-900">Dispatch runbook</h2>
            <span className={`rounded-full border px-2 py-0.5 text-xs font-medium ${severityClasses[severity] || severityClasses.info}`}>
              {severity}
            </span>
          </div>
          <p className="mt-1 text-sm text-gray-600">{runbook?.summary || 'Runbook snapshot unavailable'}</p>
        </div>
        <button
          type="button"
          onClick={onExport}
          disabled={exporting || !runbook}
          className="inline-flex items-center justify-center gap-1.5 rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 transition-colors hover:bg-gray-50 disabled:opacity-50"
        >
          <Download className="h-3.5 w-3.5" />
          Runbook
        </button>
      </div>

      <div className="mt-4 rounded-md border border-gray-200 bg-gray-50 px-3 py-2">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-xs font-semibold text-gray-900">Incident owner</p>
            {acknowledgement ? (
              <div className="mt-1 text-sm text-gray-700">
                <p>{acknowledgement.acknowledged_by_email}</p>
                {acknowledgement.note && (
                  <p className="mt-0.5 text-xs text-gray-500">{acknowledgement.note}</p>
                )}
              </div>
            ) : (
              <p className="mt-1 text-sm text-gray-500">
                {severity === 'info' ? 'No active incident to own' : 'No operator has acknowledged this incident'}
              </p>
            )}
          </div>
          {canAcknowledge && (
            <button
              type="button"
              onClick={onAcknowledge}
              disabled={acknowledging}
              className="inline-flex items-center justify-center gap-1.5 rounded-md bg-blue-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
            >
              <CheckCircle2 className="h-3.5 w-3.5" />
              Acknowledge
            </button>
          )}
          {acknowledgement && (
            <button
              type="button"
              onClick={onResolve}
              disabled={resolving}
              className="inline-flex items-center justify-center gap-1.5 rounded-md border border-green-600 bg-white px-3 py-1.5 text-xs font-medium text-green-700 transition-colors hover:bg-green-50 disabled:opacity-50"
            >
              <ShieldCheck className="h-3.5 w-3.5" />
              Resolve
            </button>
          )}
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="rounded-md bg-gray-50 px-3 py-2">
          <p className="text-xs font-medium text-gray-500">Dead-lettered</p>
          <p className="mt-1 text-lg font-semibold text-gray-900">
            {runbook?.health?.dead_lettered_executions || 0}
          </p>
        </div>
        <div className="rounded-md bg-gray-50 px-3 py-2">
          <p className="text-xs font-medium text-gray-500">Deferred retries</p>
          <p className="mt-1 text-lg font-semibold text-gray-900">
            {runbook?.health?.deferred_retries || 0}
          </p>
        </div>
        <div className="rounded-md bg-gray-50 px-3 py-2">
          <p className="text-xs font-medium text-gray-500">Channels</p>
          <p className="mt-1 text-lg font-semibold text-gray-900">
            {runbook?.policy?.configured_channels || 0}
          </p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <div>
          <p className="text-xs font-semibold text-gray-900">Recommended actions</p>
          <div className="mt-2 space-y-2">
            {actions.map((action) => (
              <div key={`${action.priority}-${action.title}`} className="rounded-md bg-gray-50 px-3 py-2 text-sm">
                <p className="font-medium text-gray-900">{action.title}</p>
                <p className="mt-1 text-xs text-gray-600">{action.detail}</p>
              </div>
            ))}
          </div>
        </div>

        <div>
          <p className="text-xs font-semibold text-gray-900">Handoff audit</p>
          <div className="mt-2 space-y-2">
            {deliveries.length === 0 && (
              <p className="text-sm text-gray-500">No recent delivery attempts</p>
            )}
            {deliveries.map((delivery) => (
              <div key={delivery.id} className="rounded-md bg-gray-50 px-3 py-2 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium text-gray-900">{delivery.alert_code}</p>
                  <span className="rounded-full bg-white px-2 py-0.5 font-medium text-gray-600">
                    {delivery.status}
                  </span>
                </div>
                <p className="mt-1 break-all text-gray-600">{delivery.target_preview}</p>
              </div>
            ))}
          </div>
        </div>
      </div>

      {incidentHistory.length > 0 && (
        <div className="mt-4">
          <p className="text-xs font-semibold text-gray-900">Incident history</p>
          <div className="mt-2 space-y-2">
            {incidentHistory.slice(0, 3).map((incident) => (
              <div key={incident.id} className="rounded-md bg-gray-50 px-3 py-2 text-xs">
                <div className="flex items-center justify-between gap-2">
                  <p className="font-medium text-gray-900">{incident.status}</p>
                  <span className="text-gray-500">{incident.severity}</span>
                </div>
                {incident.resolution_note && (
                  <p className="mt-1 text-gray-600">{incident.resolution_note}</p>
                )}
                {incident.resolved_by_email && (
                  <p className="mt-1 text-gray-500">{incident.resolved_by_email}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
