import { Copy, Link2, Plus } from 'lucide-react';

export default function WebhookTriggerPanel({
  triggers = [],
  canManage = false,
  loading = false,
  error = '',
  onCreate,
  onCopy,
}) {
  return (
    <section className="bg-white border border-gray-200 rounded-md">
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Link2 className="h-4 w-4 text-blue-600" />
          <h2 className="text-sm font-semibold text-gray-900">Webhook triggers</h2>
        </div>
        {canManage && (
          <button
            type="button"
            onClick={onCreate}
            className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
          >
            <Plus className="h-3.5 w-3.5" />
            Create webhook
          </button>
        )}
      </div>

      {error && (
        <div className="mx-4 mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      )}

      <div className="p-4 space-y-2">
        {loading && <p className="text-sm text-gray-500">Loading triggers...</p>}
        {!loading && triggers.length === 0 && (
          <p className="text-sm text-gray-500">
            No webhook triggers have been created for this workflow.
          </p>
        )}
        {triggers.map((trigger) => (
          <div
            key={trigger.id}
            className="rounded-md border border-gray-200 p-3"
          >
            <div className="flex items-center justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-gray-900">
                  {trigger.trigger_type}
                </p>
                <p className="mt-1 font-mono text-xs text-gray-600 break-all">
                  {trigger.webhook_url}
                </p>
              </div>
              <button
                type="button"
                onClick={() => onCopy?.(trigger.webhook_url)}
                className="inline-flex items-center gap-1 rounded-md border border-gray-200 px-2 py-1 text-xs text-gray-600 hover:bg-gray-50"
              >
                <Copy className="h-3.5 w-3.5" />
                Copy
              </button>
            </div>
            <p className="mt-2 text-xs text-gray-500">
              {trigger.is_active ? 'Active' : 'Inactive'} · creates a pending execution
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
