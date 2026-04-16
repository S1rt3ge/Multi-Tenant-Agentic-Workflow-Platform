import { GitBranch, Copy, Trash2, ArrowRight } from 'lucide-react';

const PATTERN_COLORS = {
  linear: 'bg-green-100 text-green-700',
  parallel: 'bg-purple-100 text-purple-700',
  cyclic: 'bg-amber-100 text-amber-700',
};

export default function WorkflowCard({ workflow, onOpen, onDuplicate, onDelete }) {
  const patternClass = PATTERN_COLORS[workflow.execution_pattern] || 'bg-gray-100 text-gray-700';

  const truncatedDesc =
    workflow.description && workflow.description.length > 100
      ? workflow.description.slice(0, 100) + '...'
      : workflow.description || 'No description';

  const updatedAt = new Date(workflow.updated_at).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow flex flex-col">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <GitBranch className="h-4 w-4 text-blue-500 flex-shrink-0" />
          <h3 className="text-sm font-semibold text-gray-900 truncate max-w-[200px]">
            {workflow.name}
          </h3>
        </div>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${patternClass}`}>
          {workflow.execution_pattern}
        </span>
      </div>

      <p className="text-sm text-gray-500 mb-4 flex-1 line-clamp-2">
        {truncatedDesc}
      </p>

      <div className="flex items-center justify-between pt-3 border-t border-gray-100">
        <span className="text-xs text-gray-400">Updated {updatedAt}</span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onOpen(workflow.id)}
            className="p-1.5 text-gray-400 hover:text-blue-600 rounded-md hover:bg-blue-50 transition-colors"
            title="Open"
          >
            <ArrowRight className="h-4 w-4" />
          </button>
          <button
            onClick={() => onDuplicate && onDuplicate(workflow.id)}
            disabled={!onDuplicate}
            className="p-1.5 text-gray-400 hover:text-purple-600 rounded-md hover:bg-purple-50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            title="Duplicate"
          >
            <Copy className="h-4 w-4" />
          </button>
          <button
            onClick={() => onDelete && onDelete(workflow.id)}
            disabled={!onDelete}
            className="p-1.5 text-gray-400 hover:text-red-600 rounded-md hover:bg-red-50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            title="Delete"
          >
            <Trash2 className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
