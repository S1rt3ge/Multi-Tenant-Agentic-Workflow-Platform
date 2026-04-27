import { useState, useEffect, useCallback } from 'react';
import { X, Save } from 'lucide-react';

const ROLES = ['retriever', 'analyzer', 'validator', 'escalator', 'custom'];
const MODELS = ['gpt-4o', 'gpt-4o-mini', 'claude-sonnet', 'claude-opus'];
const MEMORY_TYPES = ['buffer', 'summary', 'vector'];

const MODEL_LABELS = {
  'gpt-4o': 'GPT-4o',
  'gpt-4o-mini': 'GPT-4o Mini',
  'claude-sonnet': 'Claude Sonnet',
  'claude-opus': 'Claude Opus',
};

/**
 * AgentConfigPanel — right panel (320px, shown on node click).
 * Allows editing agent configuration: name, role, model, system_prompt,
 * tools, memory_type, max_tokens, temperature.
 *
 * @param {Object} props
 * @param {Object|null} props.agentConfig - Current agent config data
 * @param {Array} props.availableTools - Tools from tenant tool_registry
 * @param {Function} props.onUpdate - Called with (agentId, updateData) to save changes
 * @param {Function} props.onClose - Close the panel
 * @param {boolean} props.disabled - If viewer role — all fields disabled
 */
export default function AgentConfigPanel({
  agentConfig,
  availableTools = [],
  onUpdate,
  onClose,
  disabled = false,
}) {
  const [form, setForm] = useState({
    name: '',
    role: 'analyzer',
    model: 'gpt-4o',
    system_prompt: 'You are a helpful assistant.',
    tools: [],
    memory_type: 'buffer',
    max_tokens: 4096,
    temperature: 0.7,
  });
  const [saving, setSaving] = useState(false);

  // Sync form with selected agent config
  useEffect(() => {
    if (agentConfig) {
      setForm({
        name: agentConfig.name || '',
        role: agentConfig.role || 'analyzer',
        model: agentConfig.model || 'gpt-4o',
        system_prompt: agentConfig.system_prompt || '',
        tools: agentConfig.tools || [],
        memory_type: agentConfig.memory_type || 'buffer',
        max_tokens: agentConfig.max_tokens || 4096,
        temperature: agentConfig.temperature ?? 0.7,
      });
    }
  }, [agentConfig]);

  const handleChange = useCallback((field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  }, []);

  const handleToolToggle = useCallback(
    (tool) => {
      setForm((prev) => {
        const exists = prev.tools.some((t) => (t.id || t.tool_id) === tool.id);
        if (exists) {
          return {
            ...prev,
            tools: prev.tools.filter((t) => (t.id || t.tool_id) !== tool.id),
          };
        }
        return {
          ...prev,
          tools: [...prev.tools, { id: tool.id, name: tool.name }],
        };
      });
    },
    []
  );

  const handleApply = useCallback(async () => {
    if (!agentConfig || disabled) return;
    setSaving(true);
    try {
      await onUpdate(agentConfig.id, {
        name: form.name,
        role: form.role,
        model: form.model,
        system_prompt: form.system_prompt,
        tools: form.tools,
        memory_type: form.memory_type,
        max_tokens: form.max_tokens,
        temperature: form.temperature,
      });
    } finally {
      setSaving(false);
    }
  }, [agentConfig, form, onUpdate, disabled]);

  if (!agentConfig) return null;

  return (
    <div className="w-[320px] bg-white border-l border-gray-200 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-gray-900">Agent Config</h2>
        <button
          onClick={onClose}
          className="p-1 rounded-md text-gray-400 hover:bg-gray-100 hover:text-gray-600 transition-colors"
        >
          <X className="h-4 w-4" />
        </button>
      </div>

      {/* Form */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Name */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Name
          </label>
          <input
            type="text"
            value={form.name}
            onChange={(e) => handleChange('name', e.target.value)}
            disabled={disabled}
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 disabled:text-gray-500"
            placeholder="Agent name"
          />
        </div>

        {/* Role */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Role
          </label>
          <select
            value={form.role}
            onChange={(e) => handleChange('role', e.target.value)}
            disabled={disabled}
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 capitalize"
          >
            {ROLES.map((r) => (
              <option key={r} value={r} className="capitalize">
                {r}
              </option>
            ))}
          </select>
        </div>

        {/* Model */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Model
          </label>
          <select
            value={form.model}
            onChange={(e) => handleChange('model', e.target.value)}
            disabled={disabled}
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50"
          >
            {MODELS.map((m) => (
              <option key={m} value={m}>
                {MODEL_LABELS[m]}
              </option>
            ))}
          </select>
        </div>

        {/* System Prompt */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            System Prompt
          </label>
          <textarea
            value={form.system_prompt}
            onChange={(e) => handleChange('system_prompt', e.target.value)}
            disabled={disabled}
            rows={6}
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50 resize-none"
            placeholder="Enter system prompt for this agent..."
          />
        </div>

        {/* Tools (multi-select checkboxes) */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Tools
          </label>
          {availableTools.length === 0 ? (
            <p className="text-xs text-gray-400 italic">
              No tools registered. Add tools in the Tools page.
            </p>
          ) : (
            <div className="border border-gray-200 rounded-md max-h-[140px] overflow-y-auto">
              {availableTools.map((tool) => {
                const isSelected = form.tools.some(
                  (t) => (t.id || t.tool_id) === tool.id
                );
                return (
                  <label
                    key={tool.id}
                    className={`flex items-center gap-2 px-3 py-2 text-sm cursor-pointer hover:bg-gray-50 border-b border-gray-100 last:border-b-0 ${
                      disabled ? 'opacity-50 cursor-not-allowed' : ''
                    }`}
                  >
                    <input
                      type="checkbox"
                      checked={isSelected}
                      onChange={() => !disabled && handleToolToggle(tool)}
                      disabled={disabled}
                      className="rounded text-blue-600 focus:ring-blue-500"
                    />
                    <span className="truncate">{tool.name}</span>
                    <span className="ml-auto text-xs text-gray-400 capitalize">
                      {tool.tool_type}
                    </span>
                  </label>
                );
              })}
            </div>
          )}
        </div>

        {/* Memory Type */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Memory Type
          </label>
          <div className="flex gap-3">
            {MEMORY_TYPES.map((mt) => (
              <label
                key={mt}
                className={`flex items-center gap-1.5 text-sm cursor-pointer ${
                  disabled ? 'opacity-50 cursor-not-allowed' : ''
                }`}
              >
                <input
                  type="radio"
                  name="memory_type"
                  value={mt}
                  checked={form.memory_type === mt}
                  onChange={(e) => handleChange('memory_type', e.target.value)}
                  disabled={disabled}
                  className="text-blue-600 focus:ring-blue-500"
                />
                <span className="capitalize">{mt}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Max Tokens */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Max Tokens ({form.max_tokens})
          </label>
          <input
            type="number"
            value={form.max_tokens}
            onChange={(e) => {
              const val = parseInt(e.target.value, 10);
              if (!isNaN(val)) handleChange('max_tokens', Math.min(16384, Math.max(256, val)));
            }}
            disabled={disabled}
            min={256}
            max={16384}
            step={256}
            className="w-full px-3 py-2 text-sm border border-gray-300 rounded-md focus:ring-2 focus:ring-blue-500 focus:border-blue-500 disabled:bg-gray-50"
          />
        </div>

        {/* Temperature */}
        <div>
          <label className="block text-xs font-medium text-gray-700 mb-1">
            Temperature ({form.temperature.toFixed(1)})
          </label>
          <input
            type="range"
            value={form.temperature}
            onChange={(e) =>
              handleChange('temperature', parseFloat(e.target.value))
            }
            disabled={disabled}
            min={0}
            max={2}
            step={0.1}
            className="w-full accent-blue-600"
          />
          <div className="flex justify-between text-xs text-gray-400 mt-0.5">
            <span>Precise (0.0)</span>
            <span>Creative (2.0)</span>
          </div>
        </div>
      </div>

      {/* Apply button */}
      {!disabled && (
        <div className="px-4 py-3 border-t border-gray-200">
          <button
            onClick={handleApply}
            disabled={saving}
            className="w-full flex items-center justify-center gap-2 px-4 py-2 text-sm font-medium rounded-md bg-blue-600 text-white hover:bg-blue-700 disabled:opacity-50 transition-colors"
          >
            <Save className="h-4 w-4" />
            {saving ? 'Applying...' : 'Apply'}
          </button>
        </div>
      )}
    </div>
  );
}
