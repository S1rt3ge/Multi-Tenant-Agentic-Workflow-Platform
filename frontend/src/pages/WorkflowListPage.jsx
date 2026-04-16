import { useState, useEffect, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Plus, Search, ChevronLeft, ChevronRight, RefreshCw, GitBranch } from 'lucide-react';
import toast from 'react-hot-toast';
import useWorkflows from '../hooks/useWorkflows';
import { useAuth } from '../hooks/useAuth';
import WorkflowCard from '../components/workflow/WorkflowCard';
import CreateWorkflowModal from '../components/workflow/CreateWorkflowModal';

export default function WorkflowListPage() {
  const navigate = useNavigate();
  const { user } = useAuth();
  const isViewer = user?.role === 'viewer';
  const {
    items,
    total,
    page,
    perPage,
    search,
    loading,
    error,
    setPage,
    setSearch,
    refetch,
    create,
    duplicate,
    remove,
  } = useWorkflows();

  const [showCreate, setShowCreate] = useState(false);
  const [searchInput, setSearchInput] = useState('');

  // Debounced search (300ms)
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(searchInput);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [searchInput, setSearch, setPage]);

  const totalPages = Math.ceil(total / perPage);

  const handleOpen = useCallback(
    (id) => {
      // Builder page will come in M3; for now navigate to a detail placeholder
      navigate(`/workflows/${id}`);
    },
    [navigate]
  );

  const handleDuplicate = useCallback(
    async (id) => {
      try {
        await duplicate(id);
        toast.success('Workflow duplicated');
      } catch (err) {
        toast.error(err.response?.data?.detail || 'Failed to duplicate');
      }
    },
    [duplicate]
  );

  const handleDelete = useCallback(
    async (id) => {
      if (!window.confirm('Delete this workflow? It can be restored later.')) return;
      try {
        await remove(id);
        toast.success('Workflow deleted');
      } catch (err) {
        toast.error(err.response?.data?.detail || 'Failed to delete');
      }
    },
    [remove]
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
        <h1 className="text-2xl font-bold text-gray-900">Workflows</h1>
        <button
          onClick={() => setShowCreate(true)}
          disabled={isViewer}
          className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Plus className="h-4 w-4" />
          New Workflow
        </button>
      </div>

      {/* Search */}
      <div className="relative mb-6 max-w-sm">
        <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-gray-400" />
        <input
          type="text"
          value={searchInput}
          onChange={(e) => setSearchInput(e.target.value)}
          placeholder="Search workflows..."
          className="w-full pl-10 pr-4 py-2 rounded-lg border border-gray-300 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        />
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
          <GitBranch className="h-12 w-12 text-gray-300 mb-4" />
          <h2 className="text-lg font-medium text-gray-700 mb-2">
            {search ? 'No workflows found' : 'Create your first workflow'}
          </h2>
          <p className="text-sm text-gray-500 mb-6 max-w-sm">
            {search
              ? 'Try a different search term.'
              : 'Design agentic workflows visually and run them with a single click.'}
          </p>
          {!search && (
            <button
              onClick={() => setShowCreate(true)}
              disabled={isViewer}
              className="flex items-center gap-2 px-4 py-2 text-sm font-medium text-white bg-blue-600 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <Plus className="h-4 w-4" />
              New Workflow
            </button>
          )}
        </div>
      )}

      {/* LOADED state — card grid */}
      {!loading && items.length > 0 && (
        <>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {items.map((wf) => (
              <WorkflowCard
                key={wf.id}
                workflow={wf}
                onOpen={handleOpen}
                onDuplicate={isViewer ? undefined : handleDuplicate}
                onDelete={isViewer ? undefined : handleDelete}
              />
            ))}
          </div>

          {/* Pagination */}
          {totalPages > 1 && (
            <div className="flex items-center justify-between mt-6">
              <span className="text-sm text-gray-500">
                Showing {(page - 1) * perPage + 1}-
                {Math.min(page * perPage, total)} of {total}
              </span>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage(page - 1)}
                  disabled={page <= 1}
                  className="p-2 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronLeft className="h-4 w-4" />
                </button>
                <span className="text-sm text-gray-700">
                  Page {page} of {totalPages}
                </span>
                <button
                  onClick={() => setPage(page + 1)}
                  disabled={page >= totalPages}
                  className="p-2 rounded-lg border border-gray-300 text-gray-600 hover:bg-gray-100 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
                >
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}
        </>
      )}

      {/* Create Modal */}
      <CreateWorkflowModal
        isOpen={showCreate}
        onClose={() => setShowCreate(false)}
        onCreate={create}
      />
    </div>
  );
}
