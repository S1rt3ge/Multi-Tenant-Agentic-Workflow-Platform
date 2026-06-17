import { memo } from 'react';
import { Handle, Position } from 'reactflow';
import { Globe2, KeyRound } from 'lucide-react';

function ConnectorNode({ data, selected }) {
  const name = data.label || 'HTTP Request';
  const connector = data.connector_key || 'http';
  const action = data.action_key || 'request';
  const hasCredential = Boolean(data.credential_id);

  return (
    <div
      className={`px-4 py-3 rounded-lg border-2 shadow-sm min-w-[190px] max-w-[230px] bg-cyan-50 transition-shadow ${
        selected ? 'border-blue-500 shadow-md ring-2 ring-blue-200' : 'border-cyan-300'
      }`}
    >
      <Handle
        type="target"
        position={Position.Top}
        className="!w-3 !h-3 !bg-gray-400 !border-2 !border-white"
      />

      <div className="flex items-center gap-2 mb-2">
        <div className="p-1.5 rounded-md bg-cyan-100 text-cyan-700">
          <Globe2 className="h-4 w-4" />
        </div>
        <span className="text-sm font-medium text-gray-900 truncate flex-1">
          {name}
        </span>
      </div>

      <div className="flex items-center gap-1.5">
        <span className="text-xs px-1.5 py-0.5 rounded font-medium bg-cyan-100 text-cyan-700">
          {connector}.{action}
        </span>
        <span className="inline-flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-white text-gray-600 border border-gray-200">
          <KeyRound className="h-3 w-3" />
          {hasCredential ? 'credential' : 'no auth'}
        </span>
      </div>

      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-3 !h-3 !bg-gray-400 !border-2 !border-white"
      />
    </div>
  );
}

export default memo(ConnectorNode);
