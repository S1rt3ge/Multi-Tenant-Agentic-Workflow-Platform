import { useParams, useNavigate } from 'react-router-dom';
import { ReactFlowProvider } from 'reactflow';
import { useState, useEffect } from 'react';
import useExecution from '../hooks/useExecution';
import { getWorkflow } from '../api/workflows';
import { listAgents } from '../api/agents';
import RunPanel from '../components/execution/RunPanel';
import LogViewer from '../components/execution/LogViewer';
import ReadOnlyCanvas from '../components/execution/ReadOnlyCanvas';
import { Loader2, AlertCircle, RefreshCw, ArrowLeft } from 'lucide-react';

/**
 * ExecutionPageInner — split view: read-only canvas (left) + log panel (right).
 */
function ExecutionPageInner() {
  const { id: workflowId, executionId: execIdParam } = useParams();
  const navigate = useNavigate();

  // Workflow + agents for the read-only canvas
  const [workflow, setWorkflow] = useState(null);
  const [agentConfigs, setAgentConfigs] = useState([]);
  const [pageLoading, setPageLoading] = useState(true);
  const [pageError, setPageError] = useState(null);

  const {
    execution,
    logs,
    loading: execLoading,
    error: execError,
    isStarting,
    isCancelling,
    currentStep,
    isRunning,
    isFinished,
    canCancel,
    totalSteps,
    onStart,
    onCancel,
    refetch,
  } = useExecution(execIdParam || null, workflowId);

  // Load workflow + agents
  useEffect(() => {
    let cancelled = false;

    async function load() {
      setPageLoading(true);
      setPageError(null);
      try {
        const [wf, agents] = await Promise.all([
          getWorkflow(workflowId),
          listAgents(workflowId),
        ]);
        if (!cancelled) {
          setWorkflow(wf);
          setAgentConfigs(agents);
        }
      } catch (err) {
        if (!cancelled) {
          setPageError(err.response?.data?.detail || 'Failed to load workflow');
        }
      } finally {
        if (!cancelled) setPageLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [workflowId]);

  // Navigate to execution URL when started
  const handleStart = async (inputData) => {
    const execId = await onStart(inputData);
    if (execId) {
      navigate(`/workflows/${workflowId}/execute/${execId}`, { replace: true });
    }
  };

  // --- Loading state ---
  if (pageLoading) {
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
  if (pageError) {
    return (
      <div className="h-screen flex items-center justify-center bg-gray-50">
        <div className="flex flex-col items-center gap-3 text-center">
          <AlertCircle className="h-8 w-8 text-red-500" />
          <p className="text-sm text-red-600">{pageError}</p>
          <button
            onClick={() => window.location.reload()}
            className="flex items-center gap-2 px-4 py-2 text-sm rounded-md bg-blue-600 text-white hover:bg-blue-700 transition-colors"
          >
            <RefreshCw className="h-4 w-4" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  // Parse workflow definition for canvas
  const definition = workflow?.definition || { nodes: [], edges: [] };
  const canvasNodes = (definition.nodes || []).map((n) => {
    const config = agentConfigs.find((a) => a.node_id === n.id);
    return {
      id: n.id,
      type: 'agent',
      position: n.position || { x: 0, y: 0 },
      data: {
        label: config?.name || n.data?.label || n.id,
        role: config?.role || n.data?.role || 'analyzer',
        model: config?.model || n.data?.model || 'gpt-4o',
      },
    };
  });

  const canvasEdges = (definition.edges || []).map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    animated: true,
    style: { stroke: '#94a3b8', strokeWidth: 2 },
  }));

  // Determine which node is currently active
  const activeNodeId = currentStep
    ? agentConfigs.find((a) => a.name === currentStep.agentName)?.node_id || null
    : null;

  return (
    <div className="h-screen flex flex-col bg-gray-50">
      {/* Top bar */}
      <div className="bg-white border-b border-gray-200 px-4 py-2 flex items-center gap-3">
        <button
          onClick={() => navigate(`/workflows/${workflowId}`)}
          className="flex items-center gap-1 text-sm text-gray-500 hover:text-gray-700 transition-colors"
        >
          <ArrowLeft className="h-4 w-4" />
          Back to Builder
        </button>
        <div className="h-5 w-px bg-gray-300" />
        <h1 className="text-sm font-semibold text-gray-800">
          {workflow?.name || 'Workflow'} — Execution
        </h1>
      </div>

      {/* Run panel */}
      <RunPanel
        onStart={handleStart}
        onCancel={onCancel}
        execution={execution}
        currentStep={currentStep}
        totalSteps={totalSteps}
        isStarting={isStarting}
        isCancelling={isCancelling}
        isRunning={isRunning}
        canCancel={canCancel}
        isFinished={isFinished}
      />

      {/* Main split view */}
      <div className="flex-1 flex overflow-hidden">
        {/* Left — read-only canvas */}
        <div className="flex-1 relative">
          <ReadOnlyCanvas
            nodes={canvasNodes}
            edges={canvasEdges}
            activeNodeId={activeNodeId}
          />
        </div>

        {/* Right — log viewer */}
        <div className="w-[420px] border-l border-gray-200 bg-white flex flex-col">
          <LogViewer logs={logs} currentStep={currentStep} />
        </div>
      </div>
    </div>
  );
}

/**
 * ExecutionPage — wrapper that provides ReactFlowProvider.
 */
export default function ExecutionPage() {
  return (
    <ReactFlowProvider>
      <ExecutionPageInner />
    </ReactFlowProvider>
  );
}
