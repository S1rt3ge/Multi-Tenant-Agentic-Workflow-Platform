import { useEffect, useMemo, useState } from 'react';
import { X } from 'lucide-react';
import {
  buildHttpConnectorNodeData,
  connectorNodeToForm,
  HTTP_METHODS,
  validateHttpConnectorConfig,
} from '../../utils/connectorNode';

function FieldError({ children }) {
  if (!children) return null;
  return <p className="mt-1 text-xs text-red-600">{children}</p>;
}

export default function ConnectorConfigPanel({
  node,
  credentials = [],
  validationErrors = {},
  disabled = false,
  onUpdate,
  onClose,
}) {
  const [form, setForm] = useState(() => connectorNodeToForm(node));
  const [localErrors, setLocalErrors] = useState({});
  const errors = useMemo(
    () => ({ ...localErrors, ...validationErrors }),
    [localErrors, validationErrors]
  );

  useEffect(() => {
    setForm(connectorNodeToForm(node));
    setLocalErrors({});
  }, [node?.id]);

  const updateField = (field, value) => {
    const nextForm = { ...form, [field]: value };
    setForm(nextForm);
    const nextErrors = validateHttpConnectorConfig(nextForm);
    setLocalErrors(nextErrors);
    if (Object.keys(nextErrors).length === 0) {
      onUpdate?.(node.id, buildHttpConnectorNodeData(nextForm));
    }
  };

  return (
    <aside className="w-[360px] bg-white border-l border-gray-200 flex flex-col h-full">
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-gray-900">HTTP Request</h2>
          <p className="text-xs text-gray-500">Connector node</p>
        </div>
        {onClose && (
          <button
            type="button"
            onClick={onClose}
            className="rounded-md p-1 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          >
            <X className="h-4 w-4" />
          </button>
        )}
      </div>

      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <label className="block">
          <span className="text-xs font-medium text-gray-600">Label</span>
          <input
            value={form.label}
            onChange={(event) => updateField('label', event.target.value)}
            disabled={disabled}
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
          />
        </label>

        <label className="block">
          <span className="text-xs font-medium text-gray-600">Method</span>
          <select
            value={form.method}
            onChange={(event) => updateField('method', event.target.value)}
            disabled={disabled}
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
          >
            {HTTP_METHODS.map((method) => (
              <option key={method} value={method}>
                {method}
              </option>
            ))}
          </select>
          <FieldError>{errors.method}</FieldError>
        </label>

        <label className="block">
          <span className="text-xs font-medium text-gray-600">URL</span>
          <input
            value={form.url}
            onChange={(event) => updateField('url', event.target.value)}
            disabled={disabled}
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
            placeholder="https://example.com/api"
          />
          <FieldError>{errors.url}</FieldError>
        </label>

        <label className="block">
          <span className="text-xs font-medium text-gray-600">Credential</span>
          <select
            value={form.credentialId}
            onChange={(event) => updateField('credentialId', event.target.value)}
            disabled={disabled}
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
          >
            <option value="">No auth</option>
            {credentials.map((credential) => (
              <option key={credential.id} value={credential.id}>
                {credential.name}
              </option>
            ))}
          </select>
        </label>

        <label className="block">
          <span className="text-xs font-medium text-gray-600">Headers JSON</span>
          <textarea
            value={form.headersJson}
            onChange={(event) => updateField('headersJson', event.target.value)}
            disabled={disabled}
            rows={5}
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 font-mono text-xs"
          />
          <FieldError>{errors.headersJson}</FieldError>
        </label>

        <label className="block">
          <span className="text-xs font-medium text-gray-600">Query JSON</span>
          <textarea
            value={form.queryJson}
            onChange={(event) => updateField('queryJson', event.target.value)}
            disabled={disabled}
            rows={4}
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 font-mono text-xs"
          />
          <FieldError>{errors.queryJson}</FieldError>
        </label>

        <label className="block">
          <span className="text-xs font-medium text-gray-600">Body JSON</span>
          <textarea
            value={form.bodyJson}
            onChange={(event) => updateField('bodyJson', event.target.value)}
            disabled={disabled}
            rows={5}
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 font-mono text-xs"
          />
          <FieldError>{errors.bodyJson}</FieldError>
        </label>

        <label className="block">
          <span className="text-xs font-medium text-gray-600">Timeout seconds</span>
          <input
            value={form.timeoutSeconds}
            onChange={(event) => updateField('timeoutSeconds', event.target.value)}
            disabled={disabled}
            className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1.5 text-sm"
          />
          <FieldError>{errors.timeoutSeconds}</FieldError>
        </label>
      </div>
    </aside>
  );
}
