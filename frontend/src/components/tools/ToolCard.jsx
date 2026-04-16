import { Wrench, Pencil, Trash2, Play, Database, Globe, FolderOpen } from 'lucide-react';

const TYPE_CONFIG = {
  api: { icon: Globe, color: 'bg-blue-100 text-blue-700', label: 'API' },
  database: { icon: Database, color: 'bg-emerald-100 text-emerald-700', label: 'Database' },
  file_system: { icon: FolderOpen, color: 'bg-amber-100 text-amber-700', label: 'File System' },
};

export default function ToolCard({ tool, onEdit, onDelete, onTest }) {
  const typeConf = TYPE_CONFIG[tool.tool_type] || TYPE_CONFIG.api;
  const TypeIcon = typeConf.icon;

  const truncatedDesc =
    tool.description && tool.description.length > 120
      ? tool.description.slice(0, 120) + '...'
      : tool.description || 'No description';

  const updatedAt = new Date(tool.updated_at).toLocaleDateString('en-US', {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  return (
    <div className="bg-white rounded-xl border border-gray-200 p-5 hover:shadow-md transition-shadow flex flex-col">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <Wrench className="h-4 w-4 text-gray-500 flex-shrink-0" />
          <h3 className="text-sm font-semibold text-gray-900 truncate max-w-[200px]">
            {tool.name}
          </h3>
        </div>
        <span className={`text-xs font-medium px-2 py-0.5 rounded-full flex items-center gap-1 ${typeConf.color}`}>
          <TypeIcon className="h-3 w-3" />
          {typeConf.label}
        </span>
      </div>

      <p className="text-sm text-gray-500 mb-4 flex-1 line-clamp-2">
        {truncatedDesc}
      </p>

      {/* Config summary */}
      <div className="text-xs text-gray-400 mb-3">
        {tool.tool_type === 'api' && tool.config?.url && (
          <span className="truncate block">{tool.config.method || 'GET'} {tool.config.url}</span>
        )}
        {tool.tool_type === 'database' && tool.config?.connection_string && (
          <span className="truncate block">{tool.config.connection_string}</span>
        )}
        {tool.tool_type === 'file_system' && tool.config?.base_path && (
          <span className="truncate block">Path: {tool.config.base_path}</span>
        )}
      </div>

      <div className="flex items-center justify-between pt-3 border-t border-gray-100">
        <span className="text-xs text-gray-400">Updated {updatedAt}</span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => onTest(tool.id)}
            className="p-1.5 text-gray-400 hover:text-green-600 rounded-md hover:bg-green-50 transition-colors"
            title="Test"
          >
            <Play className="h-4 w-4" />
          </button>
          <button
            onClick={() => onEdit && onEdit(tool)}
            disabled={!onEdit}
            className="p-1.5 text-gray-400 hover:text-blue-600 rounded-md hover:bg-blue-50 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            title="Edit"
          >
            <Pencil className="h-4 w-4" />
          </button>
          <button
            onClick={() => onDelete && onDelete(tool.id)}
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
