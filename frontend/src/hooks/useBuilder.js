import { useState, useEffect, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { useNodesState, useEdgesState, addEdge } from 'reactflow';
import { getWorkflow, updateWorkflow } from '../api/workflows';
import { listAgents, createAgent, updateAgent, deleteAgent } from '../api/agents';
import { listTools } from '../api/tools';
import { validateGraph } from '../utils/graphValidation';
import toast from 'react-hot-toast';

/** Auto-save debounce delay in ms */
const AUTO_SAVE_DELAY = 2000;

/** Max undo history size */
const MAX_HISTORY = 50;

/** Generate unique node ID */
let nodeIdCounter = 0;
function generateNodeId() {
  nodeIdCounter += 1;
  return `agent_${Date.now()}_${nodeIdCounter}`;
}

/** Default names by role */
const ROLE_DEFAULTS = {
  retriever: 'Retriever',
  analyzer: 'Analyzer',
  validator: 'Validator',
  escalator: 'Escalator',
  custom: 'Custom Agent',
};

/**
 * useBuilder — main hook for the workflow builder.
 * Manages:
 * - Workflow loading (nodes, edges from definition)
 * - Agent configs CRUD
 * - Auto-save (debounce 2s)
 * - Undo/redo (50 actions)
 * - Tool list for config panel
 *
 * @param {string} workflowId - Workflow UUID
 * @returns {Object} Builder state and handlers
 */
export default function useBuilder(workflowId) {
  const navigate = useNavigate();

  // --- Core state ---
  const [workflow, setWorkflow] = useState(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [agentConfigs, setAgentConfigs] = useState([]);
  const [availableTools, setAvailableTools] = useState([]);
  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [isSaving, setIsSaving] = useState(false);
  const [hasUnsavedChanges, setHasUnsavedChanges] = useState(false);

  // --- Undo/Redo ---
  const [undoStack, setUndoStack] = useState([]);
  const [redoStack, setRedoStack] = useState([]);
  const skipHistoryRef = useRef(false);

  // --- Auto-save timer ---
  const autoSaveTimerRef = useRef(null);
  const hasUnsavedRef = useRef(false);
  const autoSaveHandlerRef = useRef(null);

  // Keep ref in sync
  useEffect(() => {
    hasUnsavedRef.current = hasUnsavedChanges;
  }, [hasUnsavedChanges]);

  // --- Push to undo stack ---
  const pushHistory = useCallback(() => {
    if (skipHistoryRef.current) return;
    setUndoStack((prev) => {
      const entry = { nodes: JSON.parse(JSON.stringify(nodes)), edges: JSON.parse(JSON.stringify(edges)) };
      const next = [...prev, entry];
      if (next.length > MAX_HISTORY) next.shift();
      return next;
    });
    setRedoStack([]);
  }, [nodes, edges]);

  // --- Load workflow + agents + tools ---
  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      setError(null);
      try {
        const [wf, agents, tools] = await Promise.all([
          getWorkflow(workflowId),
          listAgents(workflowId),
          listTools(),
        ]);

        if (cancelled) return;

        setWorkflow(wf);
        setAgentConfigs(agents);
        setAvailableTools(tools);

        // Parse definition -> nodes + edges
        const def = wf.definition || { nodes: [], edges: [] };
        const loadedNodes = (def.nodes || []).map((n) => ({
          id: n.id,
          type: 'agent',
          position: n.position || { x: 0, y: 0 },
          data: {
            label: n.data?.label || n.id,
            role: n.data?.role || 'analyzer',
            model: n.data?.model || 'gpt-4o',
          },
        }));
        const loadedEdges = (def.edges || []).map((e) => ({
          id: e.id,
          source: e.source,
          target: e.target,
          animated: true,
          style: { stroke: '#94a3b8', strokeWidth: 2 },
        }));

        // Enrich nodes with agent config data
        const configMap = new Map(agents.map((a) => [a.node_id, a]));
        loadedNodes.forEach((node) => {
          const config = configMap.get(node.id);
          if (config) {
            node.data.label = config.name;
            node.data.role = config.role;
            node.data.model = config.model;
          }
        });

        skipHistoryRef.current = true;
        setNodes(loadedNodes);
        setEdges(loadedEdges);
        skipHistoryRef.current = false;
      } catch (err) {
        if (!cancelled) {
          setError(err.response?.data?.detail || 'Failed to load workflow');
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    load();
    return () => { cancelled = true; };
  }, [workflowId, setNodes, setEdges]);

  // --- Mark changes as unsaved when nodes/edges change ---
  const initialLoadRef = useRef(true);
  useEffect(() => {
    // Skip marking unsaved on initial load
    if (initialLoadRef.current) {
      initialLoadRef.current = false;
      return;
    }
    if (loading) return;

    setHasUnsavedChanges(true);

    // Auto-save debounce
    if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current);
    autoSaveTimerRef.current = setTimeout(() => {
      if (hasUnsavedRef.current && autoSaveHandlerRef.current) {
        autoSaveHandlerRef.current(true);
      }
    }, AUTO_SAVE_DELAY);

    return () => {
      if (autoSaveTimerRef.current) clearTimeout(autoSaveTimerRef.current);
    };
  }, [nodes, edges, loading]);

  // --- Unsaved changes warning on browser close ---
  useEffect(() => {
    const handleBeforeUnload = (e) => {
      if (hasUnsavedRef.current) {
        e.preventDefault();
        e.returnValue = 'You have unsaved changes. Leave?';
      }
    };
    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => window.removeEventListener('beforeunload', handleBeforeUnload);
  }, []);

  // --- Save workflow definition ---
  const handleSave = useCallback(
    async (isAutoSave = false) => {
      if (!workflow || isSaving) return;
      setIsSaving(true);
      try {
        const definition = {
          nodes: nodes.map((n) => ({
            id: n.id,
            position: n.position,
            data: n.data,
          })),
          edges: edges.map((e) => ({
            id: e.id,
            source: e.source,
            target: e.target,
          })),
        };

        await updateWorkflow(workflow.id, { definition });
        setHasUnsavedChanges(false);
        if (!isAutoSave) {
          toast.success('Workflow saved');
        }
      } catch (err) {
        toast.error(err.response?.data?.detail || 'Failed to save workflow');
      } finally {
        setIsSaving(false);
      }
    },
    [workflow, nodes, edges, isSaving]
  );

  useEffect(() => {
    autoSaveHandlerRef.current = handleSave;
  }, [handleSave]);

  // --- Edge connect ---
  const handleConnect = useCallback(
    (params) => {
      pushHistory();
      setEdges((eds) =>
        addEdge(
          {
            ...params,
            animated: true,
            style: { stroke: '#94a3b8', strokeWidth: 2 },
          },
          eds
        )
      );
    },
    [setEdges, pushHistory]
  );

  // --- Drop new node from sidebar ---
  const handleDrop = useCallback(
    async (role, position) => {
      if (!workflow) return;

      const nodeId = generateNodeId();
      const defaultName = ROLE_DEFAULTS[role] || 'Agent';

      // Optimistically add node to canvas
      const newNode = {
        id: nodeId,
        type: 'agent',
        position,
        data: {
          label: defaultName,
          role,
          model: 'gpt-4o',
        },
      };

      pushHistory();
      setNodes((nds) => [...nds, newNode]);

      // Create agent config on backend
      try {
        const config = await createAgent(workflow.id, {
          node_id: nodeId,
          name: defaultName,
          role,
        });
        setAgentConfigs((prev) => [...prev, config]);
      } catch (err) {
        // Revert on failure
        setNodes((nds) => nds.filter((n) => n.id !== nodeId));
        const msg = err.response?.data?.detail || 'Failed to create agent';
        toast.error(msg);
      }
    },
    [workflow, setNodes, pushHistory]
  );

  // --- Delete node -> also delete agent config ---
  const handleNodeDelete = useCallback(
    async (node) => {
      if (!workflow) return;

      const config = agentConfigs.find((c) => c.node_id === node.id);
      if (config) {
        try {
          await deleteAgent(workflow.id, config.id);
          setAgentConfigs((prev) => prev.filter((c) => c.id !== config.id));
        } catch (err) {
          toast.error('Failed to delete agent configuration');
        }
      }

      // Close panel if this node was selected
      if (selectedNodeId === node.id) {
        setSelectedNodeId(null);
      }
    },
    [workflow, agentConfigs, selectedNodeId]
  );

  // --- Node click -> open config panel ---
  const handleNodeClick = useCallback((_event, node) => {
    setSelectedNodeId(node.id);
  }, []);

  // --- Update agent config ---
  const handleUpdateAgent = useCallback(
    async (agentId, data) => {
      if (!workflow) return;
      try {
        const updated = await updateAgent(workflow.id, agentId, data);
        setAgentConfigs((prev) =>
          prev.map((c) => (c.id === agentId ? updated : c))
        );

        // Update node data to reflect changes
        setNodes((nds) =>
          nds.map((n) => {
            if (n.id === updated.node_id) {
              return {
                ...n,
                data: {
                  ...n.data,
                  label: updated.name,
                  role: updated.role,
                  model: updated.model,
                },
              };
            }
            return n;
          })
        );

        toast.success('Agent configuration updated');
      } catch (err) {
        toast.error(err.response?.data?.detail || 'Failed to update agent');
        throw err;
      }
    },
    [workflow, setNodes]
  );

  // --- Close config panel ---
  const handleClosePanel = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  // --- Validate graph ---
  const handleValidate = useCallback(() => {
    const pattern = workflow?.execution_pattern || 'linear';
    const result = validateGraph(nodes, edges, agentConfigs, pattern);
    if (result.valid) {
      toast.success('Graph is valid and ready to run!');
    } else {
      result.errors.forEach((err) => toast.error(err, { duration: 5000 }));
    }
    return result;
  }, [nodes, edges, agentConfigs, workflow]);

  // --- Run (validate first, then navigate to execution page) ---
  const handleRun = useCallback(() => {
    const result = handleValidate();
    if (!result.valid) return;
    navigate(`/workflows/${workflowId}/execute`);
  }, [handleValidate, navigate, workflowId]);

  // --- Undo ---
  const handleUndo = useCallback(() => {
    if (undoStack.length === 0) return;
    const prev = undoStack[undoStack.length - 1];
    setRedoStack((r) => [...r, { nodes: JSON.parse(JSON.stringify(nodes)), edges: JSON.parse(JSON.stringify(edges)) }]);
    setUndoStack((u) => u.slice(0, -1));
    skipHistoryRef.current = true;
    setNodes(prev.nodes);
    setEdges(prev.edges);
    skipHistoryRef.current = false;
  }, [undoStack, nodes, edges, setNodes, setEdges]);

  // --- Redo ---
  const handleRedo = useCallback(() => {
    if (redoStack.length === 0) return;
    const next = redoStack[redoStack.length - 1];
    setUndoStack((u) => [...u, { nodes: JSON.parse(JSON.stringify(nodes)), edges: JSON.parse(JSON.stringify(edges)) }]);
    setRedoStack((r) => r.slice(0, -1));
    skipHistoryRef.current = true;
    setNodes(next.nodes);
    setEdges(next.edges);
    skipHistoryRef.current = false;
  }, [redoStack, nodes, edges, setNodes, setEdges]);

  // --- Keyboard shortcuts (Ctrl+S, Ctrl+Z, Ctrl+Shift+Z) ---
  useEffect(() => {
    const handleKeyDown = (e) => {
      if (e.ctrlKey || e.metaKey) {
        if (e.key === 's') {
          e.preventDefault();
          handleSave(false);
        } else if (e.key === 'z' && !e.shiftKey) {
          e.preventDefault();
          handleUndo();
        } else if ((e.key === 'z' && e.shiftKey) || e.key === 'y') {
          e.preventDefault();
          handleRedo();
        }
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleSave, handleUndo, handleRedo]);

  // --- Computed values ---
  const selectedConfig = agentConfigs.find(
    (c) => c.node_id === selectedNodeId
  );

  return {
    // State
    workflow,
    nodes,
    edges,
    agentConfigs,
    availableTools,
    selectedNodeId,
    selectedConfig,
    loading,
    error,
    isSaving,
    hasUnsavedChanges,
    canUndo: undoStack.length > 0,
    canRedo: redoStack.length > 0,

    // Node/edge handlers (for React Flow)
    onNodesChange,
    onEdgesChange,
    onConnect: handleConnect,
    onNodeClick: handleNodeClick,
    onDrop: handleDrop,
    onNodeDelete: handleNodeDelete,

    // Toolbar handlers
    onSave: () => handleSave(false),
    onRun: handleRun,
    onValidate: handleValidate,
    onUndo: handleUndo,
    onRedo: handleRedo,

    // Config panel
    onUpdateAgent: handleUpdateAgent,
    onClosePanel: handleClosePanel,

    // Reload
    refetch: () => {
      initialLoadRef.current = true;
      setLoading(true);
    },
  };
}
