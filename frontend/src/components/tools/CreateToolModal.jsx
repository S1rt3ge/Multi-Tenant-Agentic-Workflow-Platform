import { useState, useEffect } from 'react';
import toast from 'react-hot-toast';

const TOOL_TYPES = [
  { value: 'api', label: 'API' },
  { value: 'database', label: 'Database' },
  { value: 'file_system', label: 'File System' },
];

const METHODS = ['GET', 'POST', 'PUT', 'DELETE'];

function getDefaultConfig(toolType) {
  switch (toolType) {
    case 'api':
      return { url: '', method: 'GET', headers: {}, body_template: '', response_path: '' };
    case 'database':
      return { connection_string: '', query_template: '' };
    case 'file_system':
      return { base_path: '', allowed_extensions: '' };
    default:
      return {};
  }
}


function sanitizeMaskedSecrets(existingConfig, nextConfig, toolType) {
  if (!existingConfig) return nextConfig;

  if (toolType === 'api' && nextConfig.headers && typeof nextConfig.headers === 'object') {
    const mergedHeaders = { ...nextConfig.headers };
    Object.entries(mergedHeaders).forEach(([key, value]) => {
      if (typeof value === 'string' && value.includes('****') && existingConfig.headers?.[key]) {
        mergedHeaders[key] = existingConfig.headers[key];
      }
    });
    return { ...nextConfig, headers: mergedHeaders };
  }

  if (
    toolType === 'database' &&
    typeof nextConfig.connection_string === 'string' &&
    nextConfig.connection_string.includes('****') &&
    existingConfig.connection_string
  ) {
    return {
      ...nextConfig,
      connection_string: existingConfig.connection_string,
    };
  }

  return nextConfig;
}

export default function CreateToolModal({ isOpen, onClose, onSubmit, editTool }) {
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [toolType, setToolType] = useState('api');
  const [config, setConfig] = useState(getDefaultConfig('api'));
  const [headerKey, setHeaderKey] = useState('');
  const [headerValue, setHeaderValue] = useState('');
  const [submitting, setSubmitting] = useState(false);

  // Populate form when editing
  useEffect(() => {
    if (editTool) {
      setName(editTool.name);
      setDescription(editTool.description || '');
      setToolType(editTool.tool_type);
      setConfig(editTool.config || getDefaultConfig(editTool.tool_type));
    } else {
      setName('');
      setDescription('');
      setToolType('api');
      setConfig(getDefaultConfig('api'));
    }
    setHeaderKey('');
    setHeaderValue('');
  }, [editTool, isOpen]);

  if (!isOpen) return null;

  const updateConfig = (key, value) => {
    setConfig((prev) => ({ ...prev, [key]: value }));
  };

  const addHeader = () => {
    if (!headerKey.trim()) return;
    setConfig((prev) => ({
      ...prev,
      headers: { ...prev.headers, [headerKey.trim()]: headerValue },
    }));
    setHeaderKey('');
    setHeaderValue('');
  };

  const removeHeader = (key) => {
    setConfig((prev) => {
      const headers = { ...prev.headers };
      delete headers[key];
      return { ...prev, headers };
    });
  };

  const handleTypeChange = (newType) => {
    setToolType(newType);
    setConfig(getDefaultConfig(newType));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!name.trim()) return;

    setSubmitting(true);
    try {
      const payload = {
        name: name.trim(),
        description: description.trim(),
        tool_type: toolType,
        config: sanitizeMaskedSecrets(editTool?.config, config, toolType),
      };
      await onSubmit(payload, editTool?.id);
      toast.success(editTool ? 'Tool updated' : 'Tool created');
      onClose();
    } catch (err) {
      toast.error(err.response?.data?.detail || 'Failed to save tool');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40">
      <div className="bg-white rounded-xl shadow-xl w-full max-w-lg p-6 max-h-[90vh] overflow-y-auto">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">
          {editTool ? 'Edit Tool' : 'Add Tool'}
        </h2>
        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Name <span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              placeholder="My API Tool"
              maxLength={255}
              autoFocus
            />
          </div>

          {/* Description */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
              placeholder="Optional description..."
              rows={2}
              maxLength={2000}
            />
          </div>

          {/* Type */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Type
            </label>
            <select
              value={toolType}
              onChange={(e) => handleTypeChange(e.target.value)}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              disabled={!!editTool}
            >
              {TOOL_TYPES.map((t) => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>

          {/* Dynamic config form */}
          <div className="border border-gray-200 rounded-lg p-4 space-y-3 bg-gray-50">
            <h3 className="text-sm font-medium text-gray-700">Configuration</h3>

            {toolType === 'api' && (
              <>
                <div>
                  <label className="block text-xs text-gray-600 mb-1">URL <span className="text-red-500">*</span></label>
                  <input
                    type="text"
                    value={config.url || ''}
                    onChange={(e) => updateConfig('url', e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="https://api.example.com/endpoint"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-600 mb-1">Method</label>
                  <select
                    value={config.method || 'GET'}
                    onChange={(e) => updateConfig('method', e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                  >
                    {METHODS.map((m) => (
                      <option key={m} value={m}>{m}</option>
                    ))}
                  </select>
                </div>
                {/* Headers */}
                <div>
                  <label className="block text-xs text-gray-600 mb-1">Headers</label>
                  {config.headers && Object.keys(config.headers).length > 0 && (
                    <div className="space-y-1 mb-2">
                      {Object.entries(config.headers).map(([k, v]) => (
                        <div key={k} className="flex items-center gap-2 text-xs">
                          <span className="font-mono bg-white rounded px-2 py-1 border flex-1 truncate">{k}: {v}</span>
                          <button
                            type="button"
                            onClick={() => removeHeader(k)}
                            className="text-red-400 hover:text-red-600 text-xs"
                          >
                            Remove
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={headerKey}
                      onChange={(e) => setHeaderKey(e.target.value)}
                      placeholder="Key"
                      className="flex-1 rounded-lg border border-gray-300 px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <input
                      type="text"
                      value={headerValue}
                      onChange={(e) => setHeaderValue(e.target.value)}
                      placeholder="Value"
                      className="flex-1 rounded-lg border border-gray-300 px-2 py-1 text-xs focus:outline-none focus:ring-2 focus:ring-blue-500"
                    />
                    <button
                      type="button"
                      onClick={addHeader}
                      className="px-2 py-1 text-xs font-medium text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                    >
                      Add
                    </button>
                  </div>
                </div>
                <div>
                  <label className="block text-xs text-gray-600 mb-1">Body Template</label>
                  <textarea
                    value={config.body_template || ''}
                    onChange={(e) => updateConfig('body_template', e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                    placeholder='{"query": "{input}"}'
                    rows={2}
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-600 mb-1">Response Path (JSONPath)</label>
                  <input
                    type="text"
                    value={config.response_path || ''}
                    onChange={(e) => updateConfig('response_path', e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="$.data.results"
                  />
                </div>
              </>
            )}

            {toolType === 'database' && (
              <>
                <div>
                  <label className="block text-xs text-gray-600 mb-1">
                    Connection String <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={config.connection_string || ''}
                    onChange={(e) => updateConfig('connection_string', e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="postgresql://user:pass@host:5432/db"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-600 mb-1">Query Template</label>
                  <textarea
                    value={config.query_template || ''}
                    onChange={(e) => updateConfig('query_template', e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
                    placeholder="SELECT * FROM users WHERE id = {input}"
                    rows={2}
                  />
                </div>
              </>
            )}

            {toolType === 'file_system' && (
              <>
                <div>
                  <label className="block text-xs text-gray-600 mb-1">
                    Base Path <span className="text-red-500">*</span>
                  </label>
                  <input
                    type="text"
                    value={config.base_path || ''}
                    onChange={(e) => updateConfig('base_path', e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder="/data/uploads"
                  />
                </div>
                <div>
                  <label className="block text-xs text-gray-600 mb-1">
                    Allowed Extensions (comma-separated)
                  </label>
                  <input
                    type="text"
                    value={config.allowed_extensions || ''}
                    onChange={(e) => updateConfig('allowed_extensions', e.target.value)}
                    className="w-full rounded-lg border border-gray-300 px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
                    placeholder=".csv, .json, .txt"
                  />
                </div>
              </>
            )}
          </div>

          {/* Actions */}
          <div className="flex justify-end gap-3 pt-2">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 text-sm text-gray-600 hover:text-gray-800 transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={submitting || !name.trim()}
              className="px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              {submitting ? 'Saving...' : editTool ? 'Save Changes' : 'Create'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
