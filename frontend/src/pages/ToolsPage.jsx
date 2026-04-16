import { useState, useCallback } from 'react';
import { Plus, RefreshCw, Wrench } from 'lucide-react';
import toast from 'react-hot-toast';
import useTools from '../hooks/useTools';
import { useAuth } from '../hooks/useAuth';
import ToolCard from '../components/tools/ToolCard';
import CreateToolModal from '../components/tools/CreateToolModal';

export default function ToolsPage() {
  const { items, loading, error, refetch, create, update, remove, test } = useTools();
  const { user } = useAuth();
  const isViewer = user?.role === 'viewer';

  const [showModal, setShowModal] = useState(false);
  const [editTool, setEditTool] = useState(null);

  const handleOpenCreate = () => {
    setEditTool(null);
    setShowModal(true);
  };

  const handleOpenEdit = (tool) => {
    setEditTool(tool);
    setShowModal(true);
  };

  const handleSubmit = useCallback(
    async (data, toolId) => {
      if (toolId) {
        await update(toolId, data);
      } else {
        await create(data);
      }
    },
    [create, update]
  );

  const handleDelete = useCallback(
    async (id) => {
      if (!window.confirm('Delete this tool?')) return;
      try {
        await remove(id);
        toast.success('Tool deleted');
      } catch (err) {
        toast.error(err.response?.data?.detail || 'Failed to delete');
      }
    },
    [remove]
  );

  const handleTest = useCallback(
    async (id) => {
      const tid = toast.loading('Testing tool...');
      try {
        const result = await test(id);
        toast.dismiss(tid);
        if (result.success) {
          toast.success(`Test passed (${result.latency_ms}ms)`);
        } else {
          toast.error(`Test failed: ${typeof result.response === 'string' ? result.response : JSON.stringify(result.response)}`);
        }
      } catch (err) {
        toast.dismiss(tid);
        toast.error(err.response?.data?.detail || 'Test request failed');
      }
    },
    [test]
  );

  // --- ERROR state ---
  if (error && !loading) {
    return (
      <div className="p-8 flex flex-col items-center justify-center min-h-[400px]">
        <p className="text-red-500 mb-4">{error}</p>
        <button
          onClick={refetch}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors"
        >
          <RefreshCw className="h-4 w-4" />
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="p-8">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Tools</h1>
        <button
          onClick={handleOpenCreate}
          disabled={isViewer}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Plus className="h-4 w-4" />
          Add Tool
        </button>
      </div>

      {/* LOADING state — skeleton cards */}
      {loading && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[...Array(6)].map((_, i) => (
            <div
              key={i}
              className="bg-white rounded-xl border border-gray-200 p-5 animate-pulse"
            >
              <div className="h-4 bg-gray-200 rounded w-2/3 mb-3" />
              <div className="h-3 bg-gray-100 rounded w-full mb-2" />
              <div className="h-3 bg-gray-100 rounded w-4/5 mb-4" />
              <div className="h-8 bg-gray-50 rounded mt-3" />
            </div>
          ))}
        </div>
      )}

      {/* EMPTY state */}
      {!loading && items.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20 text-center">
          <Wrench className="h-12 w-12 text-gray-300 mb-4" />
          <h2 className="text-lg font-medium text-gray-700 mb-2">
            No tools registered yet
          </h2>
          <p className="text-sm text-gray-500 mb-6 max-w-sm">
            Register API endpoints, databases, or file systems as tools so your agents can use them.
          </p>
          <button
            onClick={handleOpenCreate}
            disabled={isViewer}
            className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            <Plus className="h-4 w-4" />
            Add Tool
          </button>
        </div>
      )}

      {/* LOADED state — card grid */}
      {!loading && items.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {items.map((tool) => (
            <ToolCard
              key={tool.id}
              tool={tool}
              onEdit={isViewer ? undefined : handleOpenEdit}
              onDelete={isViewer ? undefined : handleDelete}
              onTest={handleTest}
            />
          ))}
        </div>
      )}

      {/* Create/Edit Modal */}
      <CreateToolModal
        isOpen={showModal}
        onClose={() => {
          setShowModal(false);
          setEditTool(null);
        }}
        onSubmit={handleSubmit}
        editTool={editTool}
      />
    </div>
  );
}
