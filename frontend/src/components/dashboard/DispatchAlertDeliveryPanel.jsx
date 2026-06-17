import { History, RadioTower, ShieldCheck } from 'lucide-react';

export default function DispatchAlertDeliveryPanel({ channels, deliveries }) {
  if (!channels || !deliveries) return null;

  return (
    <section className="bg-white rounded-xl border border-gray-200 p-5">
      <div className="mb-4 flex items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-gray-900">Delivery adapters</h3>
          <p className="mt-1 text-xs text-gray-500">Encrypted channels and sanitized audit trail</p>
        </div>
        <div className="rounded-lg bg-blue-50 p-2 text-blue-600">
          <RadioTower className="h-4 w-4" />
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
        <div className="rounded-lg border border-gray-100 p-3">
          <div className="mb-3 flex items-center gap-2">
            <ShieldCheck className="h-3.5 w-3.5 text-emerald-600" />
            <p className="text-xs font-semibold text-gray-900">Channels</p>
          </div>
          {channels.length === 0 ? (
            <p className="text-sm text-gray-500">No delivery channels configured</p>
          ) : (
            <div className="space-y-2">
              {channels.map((channel) => (
                <div key={channel.id} className="rounded-md bg-gray-50 px-3 py-2">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-sm font-medium text-gray-900">{channel.name}</p>
                      <p className="mt-0.5 text-xs text-gray-500">{channel.channel_type}</p>
                      {channel.config_preview?.url && (
                        <p className="mt-1 break-all text-xs text-gray-600">
                          {channel.config_preview.url}
                        </p>
                      )}
                    </div>
                    <span className="shrink-0 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-medium text-emerald-700">
                      encrypted
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="rounded-lg border border-gray-100 p-3">
          <div className="mb-3 flex items-center gap-2">
            <History className="h-3.5 w-3.5 text-blue-600" />
            <p className="text-xs font-semibold text-gray-900">Recent delivery audit</p>
          </div>
          {deliveries.length === 0 ? (
            <p className="text-sm text-gray-500">No delivery attempts yet</p>
          ) : (
            <div className="space-y-2">
              {deliveries.map((delivery) => (
                <div key={delivery.id} className="rounded-md bg-gray-50 px-3 py-2 text-xs">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-medium text-gray-900">{delivery.alert_code}</p>
                      <p className="mt-0.5 break-all text-gray-600">{delivery.target_preview}</p>
                    </div>
                    <span
                      className={`shrink-0 rounded-full border px-2 py-0.5 font-medium ${
                        delivery.status === 'delivered'
                          ? 'border-emerald-200 bg-emerald-50 text-emerald-700'
                          : 'border-red-200 bg-red-50 text-red-700'
                      }`}
                    >
                      {delivery.status}
                    </span>
                  </div>
                  {delivery.status_code && (
                    <p className="mt-1 text-gray-500">HTTP {delivery.status_code}</p>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </section>
  );
}
