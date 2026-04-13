import { useParams } from 'react-router-dom';
import { ReactFlowProvider, useReactFlow } from 'reactflow';
import useBuilder from '../hooks/useBuilder';
import Sidebar from '../components/builder/Sidebar';
import Canvas from '../components/builder/Canvas';
import AgentConfigPanel from '../components/builder/AgentConfigPanel';
import Toolbar from '../components/builder/Toolbar';
import { useAuth } from '../hooks/useAuth';
import { Loader2, AlertCircle, RefreshCw } from 'lucide-react';

/**
 * BuilderPageInner — the actual builder layout.
 * Must be inside ReactFlowProvider to use useReactFlow().
 */
function BuilderPageInner() {
  const { id: workflowId } = useParams();
  const { user } = useAuth();
  const isViewer = user?.role === 'viewer';

  const {
    workflow,
    nodes,
    edges,
    availableTools,
    selectedConfig,
    loading,
    error,
    isSaving,
    hasUnsavedChanges,
    canUndo,
    canRedo,
    onNodesChange,
    onEdgesChange,
    onConnect,
    onNodeClick,
    onDrop,
    onNodeDelete,
    onSave,
    onRun,
    onValidate,
    onUndo,
    onRedo,
    onUpdateAgent,
    onClosePanel,
    refetch,
  } = useBuilder(workflowId);

  const { zoomIn, zoomOut, fitView } = useReactFlow();

  // --- Loading state ---
  if (loading) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center gap-3">
          <Loader2 className="h-8 w-8 text-blue-600 animate-spin" />
          <p className="text-sm text-gray-500">Loading workflow...</p>
        </div>
      </div>
    );
  }

  // --- Error state ---
  if (error) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center gap-3 text-center">
          <AlertCircle className="h-8 w-8 text-red-500" />
          <p className="text-sm text-red-600">{error}</p>
          <button
            onClick={refetch}
            className="flex items-center gap-2 px-4 py-2 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700 transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Toolbar */}
      <Toolbar
        onSave={onSave}
        onRun={onRun}
        onValidate={onValidate}
        onUndo={onUndo}
        onRedo={onRedo}
        onZoomIn={zoomIn}
        onZoomOut={zoomOut}
        onFitView={() => fitView({ padding: 0.2 })}
        canUndo={canUndo}
        canRedo={canRedo}
        isSaving={isSaving}
        hasUnsavedChanges={hasUnsavedChanges}
        disabled={isViewer}
        workflowName={workflow?.name || 'Workflow'}
      />

      {/* Main area: Sidebar + Canvas + Config Panel */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left sidebar — node palette */}
        <Sidebar disabled={isViewer} />

        {/* Center — React Flow canvas */}
        <Canvas
          nodes={nodes}
          edges={edges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={onNodeClick}
          onDrop={onDrop}
          onNodeDelete={onNodeDelete}
          executionPattern={workflow?.execution_pattern || 'linear'}
          disabled={isViewer}
        />

        {/* Right panel — agent config (shown when a node is selected) */}
        {selectedConfig && (
          <AgentConfigPanel
            agentConfig={selectedConfig}
            availableTools={availableTools}
            onUpdate={onUpdateAgent}
            onClose={onClosePanel}
            disabled={isViewer}
          />
        )}
      </div>
    </div>
  );
}

/**
 * BuilderPage — wrapper that provides ReactFlowProvider.
 * The builder page does NOT use the Layout component (no app sidebar) —
 * it has its own full-screen layout with toolbar + sidebar + canvas + config panel.
 */
export default function BuilderPage() {
  return (
    <ReactFlowProvider>
      <BuilderPageInner />
    </ReactFlowProvider>
  );
}
