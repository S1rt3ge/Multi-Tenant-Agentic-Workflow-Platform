import { BellRing, Mail, Route, ShieldCheck } from 'lucide-react';

function formatList(values = []) {
  return values.length ? values.join(', ') : 'None';
}

export default function DispatchAlertPolicyPanel({ policy, preview }) {
  if (!policy || !preview) return null;

  const enabledChannels = policy.channels.filter((channel) => channel.enabled);

  return (
    <section className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">Alert routing</h3>
          <p className="mt-1 text-xs text-gray-500">Dry-run notification policy for dispatch alerts</p>
        </div>
        <span
          className={`rounded-full border px-2 py-1 text-xs font-medium ${
            policy.enabled
              ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
              : 'border-gray-200 bg-gray-50 text-gray-600'
          }`}
        >
          {policy.enabled ? 'Enabled' : 'Disabled'}
        </span>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3">
        <div className="rounded-lg border border-gray-100 px-3 py-3">
          <div className="mb-2 inline-flex rounded-md bg-blue-50 p-1.5 text-blue-600">
            <BellRing className="h-3.5 w-3.5" />
          </div>
          <p className="text-xs font-medium text-gray-500">Alert filters</p>
          <p className="mt-1 text-sm text-gray-900">{formatList(policy.alert_codes)}</p>
          <p className="mt-1 text-xs text-gray-500">{formatList(policy.severities)}</p>
        </div>

        <div className="rounded-lg border border-gray-100 px-3 py-3">
          <div className="mb-2 inline-flex rounded-md bg-emerald-50 p-1.5 text-emerald-600">
            <Mail className="h-3.5 w-3.5" />
          </div>
          <p className="text-xs font-medium text-gray-500">Channels</p>
          {enabledChannels.length === 0 ? (
            <p className="mt-1 text-sm text-gray-500">No channels configured</p>
          ) : (
            <div className="mt-1 space-y-1">
              {enabledChannels.map((channel) => (
                <p key={`${channel.type}:${channel.target}`} className="text-sm text-gray-900 break-all">
                  {channel.type}: {channel.target}
                </p>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-lg border border-gray-100 px-3 py-3">
          <div className="mb-2 inline-flex rounded-md bg-gray-50 p-1.5 text-gray-600">
            <ShieldCheck className="h-3.5 w-3.5" />
          </div>
          <p className="text-xs font-medium text-gray-500">Cooldown</p>
          <p className="mt-1 text-sm text-gray-900">{policy.cooldown_minutes} minutes</p>
          <p className="mt-1 text-xs text-gray-500">No external delivery in this slice</p>
        </div>
      </div>

      <div className="mt-4 rounded-lg border border-gray-100 px-3 py-3">
        <div className="mb-2 flex items-center gap-2">
          <Route className="h-3.5 w-3.5 text-blue-600" />
          <p className="text-xs font-semibold text-gray-900">Dry-run preview</p>
        </div>

        {preview.routes.length === 0 ? (
          <p className="text-sm text-gray-500">No routes planned</p>
        ) : (
          <div className="space-y-2">
            {preview.routes.map((route) => (
              <div
                key={`${route.channel_type}:${route.target}`}
                className="rounded-md bg-gray-50 px-3 py-2 text-xs text-gray-700"
              >
                <p className="font-medium text-gray-900 break-all">
                  {route.channel_type}: {route.target}
                </p>
                <p className="mt-1">Alerts: {formatList(route.alert_codes)}</p>
              </div>
            ))}
          </div>
        )}

        {preview.alerts.length > 0 && (
          <div className="mt-3 space-y-1">
            {preview.alerts.map((alert) => (
              <p key={alert.code} className="text-xs text-gray-600">
                {alert.title} ({alert.code})
              </p>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
