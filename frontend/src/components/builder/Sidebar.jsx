import { Search, BarChart3, ShieldCheck, AlertTriangle, Cpu } from 'lucide-react';

/**
 * Palette sections — draggable node types grouped by role.
 */
const NODE_PALETTE = [
  {
    title: 'Retriever',
    role: 'retriever',
    icon: Search,
    description: 'Fetch data from APIs, databases, or files',
    color: 'text-blue-600 bg-blue-50 border-blue-200',
  },
  {
    title: 'Analyzer',
    role: 'analyzer',
    icon: BarChart3,
    description: 'Process and analyze data',
    color: 'text-purple-600 bg-purple-50 border-purple-200',
  },
  {
    title: 'Validator',
    role: 'validator',
    icon: ShieldCheck,
    description: 'Validate and verify results',
    color: 'text-green-600 bg-green-50 border-green-200',
  },
  {
    title: 'Escalator',
    role: 'escalator',
    icon: AlertTriangle,
    description: 'Handle exceptions and escalate issues',
    color: 'text-orange-600 bg-orange-50 border-orange-200',
  },
  {
    title: 'Custom',
    role: 'custom',
    icon: Cpu,
    description: 'Generic agent with custom behavior',
    color: 'text-gray-600 bg-gray-50 border-gray-200',
  },
];

/**
 * Handle drag start — encode node type data for React Flow drop.
 */
function onDragStart(event, role) {
  event.dataTransfer.setData('application/reactflow', role);
  event.dataTransfer.effectAllowed = 'move';
}

/**
 * Sidebar — left panel (280px) with draggable node palette.
 * Each item is draggable onto the canvas to create a new agent node.
 *
 * @param {Object} props
 * @param {boolean} props.disabled - If true (viewer role), disable dragging
 */
export default function Sidebar({ disabled = false }) {
  return (
    <div className="w-[280px] bg-white border-r border-gray-200 flex flex-col h-full overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-gray-200">
        <h2 className="text-sm font-semibold text-gray-900">Agent Palette</h2>
        <p className="text-xs text-gray-500 mt-0.5">
          Drag agents onto the canvas
        </p>
      </div>

      {/* Node palette */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {NODE_PALETTE.map((item) => {
          const Icon = item.icon;
          return (
            <div
              key={item.role}
              draggable={!disabled}
              onDragStart={(e) => !disabled && onDragStart(e, item.role)}
              className={`flex items-start gap-3 p-3 rounded-lg border transition-colors ${
                item.color
              } ${
                disabled
                  ? 'opacity-50 cursor-not-allowed'
                  : 'cursor-grab active:cursor-grabbing hover:shadow-sm'
              }`}
            >
              <div className="p-1.5 rounded-md bg-white/70 flex-shrink-0">
                <Icon className="h-4 w-4" />
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium leading-tight">
                  {item.title}
                </p>
                <p className="text-xs opacity-70 mt-0.5 leading-snug">
                  {item.description}
                </p>
              </div>
            </div>
          );
        })}
      </div>

      {/* Footer hint */}
      {!disabled && (
        <div className="px-4 py-3 border-t border-gray-200">
          <p className="text-xs text-gray-400 text-center">
            Drag & drop to add agents to workflow
          </p>
        </div>
      )}
    </div>
  );
}
