import { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { Search, BarChart3, ShieldCheck, AlertTriangle, Cpu } from 'lucide-react';

/**
 * Role icon mapping for agent nodes.
 */
const ROLE_ICONS = {
  retriever: Search,
  analyzer: BarChart3,
  validator: ShieldCheck,
  escalator: AlertTriangle,
  custom: Cpu,
};

/**
 * Role color mapping (Tailwind classes).
 */
const ROLE_COLORS = {
  retriever: { bg: 'bg-blue-50', border: 'border-blue-300', icon: 'text-blue-600', badge: 'bg-blue-100 text-blue-700' },
  analyzer: { bg: 'bg-purple-50', border: 'border-purple-300', icon: 'text-purple-600', badge: 'bg-purple-100 text-purple-700' },
  validator: { bg: 'bg-green-50', border: 'border-green-300', icon: 'text-green-600', badge: 'bg-green-100 text-green-700' },
  escalator: { bg: 'bg-orange-50', border: 'border-orange-300', icon: 'text-orange-600', badge: 'bg-orange-100 text-orange-700' },
  custom: { bg: 'bg-gray-50', border: 'border-gray-300', icon: 'text-gray-600', badge: 'bg-gray-100 text-gray-700' },
};

/**
 * Model display names.
 */
const MODEL_LABELS = {
  'gpt-4o': 'GPT-4o',
  'gpt-4o-mini': 'GPT-4o Mini',
  'claude-sonnet': 'Claude Sonnet',
  'claude-opus': 'Claude Opus',
};

/**
 * Custom React Flow node for agents.
 * Displays: role icon, agent name, model badge, input/output handles.
 */
function AgentNode({ data, selected }) {
  const role = data.role || 'analyzer';
  const model = data.model || 'gpt-4o';
  const name = data.label || 'Agent';

  const Icon = ROLE_ICONS[role] || Cpu;
  const colors = ROLE_COLORS[role] || ROLE_COLORS.custom;

  return (
    <div
      className={`px-4 py-3 rounded-lg border-2 shadow-sm min-w-[180px] max-w-[220px] transition-shadow ${
        colors.bg
      } ${selected ? 'border-blue-500 shadow-md ring-2 ring-blue-200' : colors.border}`}
    >
      {/* Input handle (top) */}
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !bg-gray-400 !border-2 !border-white"
      />

      {/* Node content */}
      <div className="flex items-center gap-2 mb-2">
        <div className={`p-1.5 rounded-md ${colors.badge}`}>
          <Icon className="h-4 w-4" />
        </div>
        <span className="text-sm font-medium text-gray-900 truncate flex-1">
          {name}
        </span>
      </div>

      {/* Role + Model badges */}
      <div className="flex items-center gap-1.5">
        <span
          className={`text-xs px-1.5 py-0.5 rounded font-medium capitalize ${colors.badge}`}
        >
          {role}
        </span>
        <span className="text-xs px-1.5 py-0.5 rounded bg-white text-gray-600 border border-gray-200">
          {MODEL_LABELS[model] || model}
        </span>
      </div>

      {/* Output handle (bottom) */}
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-gray-400 !border-2 !border-white"
      />
    </div>
  );
}

export default memo(AgentNode);
