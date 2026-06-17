import { useState } from 'react';
import { KeyRound, Plus, Trash2 } from 'lucide-react';

const DEFAULT_FORM = {
  connectorKey: 'http',
  name: '',
  headerName: 'Authorization',
  headerValue: '',
};

export function buildCredentialPayload(form) {
  return {
    connector_key: form.connectorKey || 'http',
    name: form.name,
    auth_type: 'api_key_header',
    config: {
      header_name: form.headerName || 'Authorization',
      header_value: form.headerValue,
    },
  };
}

export function clearCredentialSecret(form) {
  return { ...form, headerValue: '' };
}

export default function CredentialManager({
  credentials = [],
  canManage = false,
  loading = false,
  error = '',
  onCreate,
  onDelete,
}) {
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState(DEFAULT_FORM);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (!onCreate || submitting) return;
    setSubmitting(true);
    try {
      await onCreate(buildCredentialPayload(form));
      setForm((current) => clearCredentialSecret({ ...current, name: '' }));
      setShowCreate(false);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="h-full flex flex-col bg-white">
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <KeyRound className="h-4 w-4 text-blue-600" />
          <h2 className="text-sm font-semibold text-gray-900">Credentials</h2>
        </div>
        {canManage && (
          <button
            type="button"
            onClick={() => setShowCreate((value) => !value)}
            className="inline-flex items-center gap-1.5 rounded-md bg-blue-600 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-blue-700"
          >
            <Plus className="h-3.5 w-3.5" />
            Create credential
          </button>
        )}
      </div>

      {error && (
        <div className="mx-4 mt-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">
          {error}
        </div>
      )}

      {showCreate && canManage && (
        <form onSubmit={handleSubmit} className="border-b border-gray-200 p-4 space-y-3">
          <label className="block">
            <span className="text-xs font-medium text-gray-600">Name</span>
            <input
              value={form.name}
              onChange={(event) =>
                setForm((current) => ({ ...current, name: event.target.value }))
              }
              className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
              placeholder="Example API"
              required
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-gray-600">Header name</span>
            <input
              value={form.headerName}
              onChange={(event) =>
                setForm((current) => ({ ...current, headerName: event.target.value }))
              }
              className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
              required
            />
          </label>
          <label className="block">
            <span className="text-xs font-medium text-gray-600">Header value</span>
            <input
              type="password"
              value={form.headerValue}
              onChange={(event) =>
                setForm((current) => ({ ...current, headerValue: event.target.value }))
              }
              className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
              placeholder="Bearer ..."
              required
            />
          </label>
          <button
            type="submit"
            disabled={submitting}
            className="rounded-md bg-gray-900 px-3 py-1.5 text-xs font-medium text-white disabled:opacity-60"
          >
            Save credential
          </button>
        </form>
      )}

      <div className="flex-1 overflow-y-auto p-4 space-y-2">
        {loading && <p className="text-sm text-gray-500">Loading credentials...</p>}
        {!loading && credentials.length === 0 && (
          <p className="text-sm text-gray-500">No credentials yet.</p>
        )}
        {credentials.map((credential) => (
          <div
            key={credential.id}
            className="rounded-md border border-gray-200 p-3"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-gray-900 truncate">
                  {credential.name}
                </p>
                <p className="text-xs text-gray-500">
                  {credential.connector_key} / {credential.auth_type}
                </p>
              </div>
              {canManage && (
                <button
                  type="button"
                  onClick={() => onDelete?.(credential.id)}
                  className="inline-flex items-center gap-1 rounded-md border border-gray-200 px-2 py-1 text-xs text-gray-600 hover:bg-gray-50"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  Delete
                </button>
              )}
            </div>
            {credential.config_preview && (
              <dl className="mt-2 grid grid-cols-[90px_1fr] gap-x-2 gap-y-1 text-xs">
                {Object.entries(credential.config_preview).map(([key, value]) => (
                  <div key={key} className="contents">
                    <dt className="text-gray-500">{key}</dt>
                    <dd className="font-mono text-gray-700 break-all">{String(value)}</dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
        ))}
      </div>
    </section>
  );
}
