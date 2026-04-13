import { useCallback, useRef } from 'react';
import ReactFlow, {
  Background,
  MiniMap,
  Controls,
  useReactFlow,
} from 'reactflow';
import 'reactflow/dist/style.css';
import AgentNode from './AgentNode';
import toast from 'react-hot-toast';
import { isDuplicateEdge, isSelfLoop } from '../../utils/graphValidation';

/**
 * Custom node types registration for React Flow.
 */
const nodeTypes = { agent: AgentNode };

/**
 * Default edge options — animated, styled.
 */
const defaultEdgeOptions = {
  animated: true,
  style: { stroke: '#94a3b8', strokeWidth: 2 },
};

/**
 * Canvas — React Flow canvas (center area).
 * Handles drag-and-drop from sidebar, edge creation, node selection.
 *
 * @param {Object} props
 * @param {Array} props.nodes - React Flow nodes
 * @param {Array} props.edges - React Flow edges
 * @param {Function} props.onNodesChange - Node change handler
 * @param {Function} props.onEdgesChange - Edge change handler
 * @param {Function} props.onConnect - Edge connect handler
 * @param {Function} props.onNodeClick - Node click handler (opens config panel)
 * @param {Function} props.onDrop - Drop handler for new nodes from sidebar
 * @param {Function} props.onNodeDelete - Called when a node is deleted
 * @param {string} props.executionPattern - 'linear' | 'parallel' | 'cyclic'
 * @param {boolean} props.disabled - If viewer role — disable interactions
 */
export default function Canvas({
  nodes,
  edges,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onNodeClick,
  onDrop,
  onNodeDelete,
  executionPattern = 'linear',
  disabled = false,
}) {
  const reactFlowWrapper = useRef(null);
  const { screenToFlowPosition } = useReactFlow();

  /**
   * Handle drag over — allow drop.
   */
  const handleDragOver = useCallback((event) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = 'move';
  }, []);

  /**
   * Handle drop from sidebar — create a new node.
   */
  const handleDrop = useCallback(
    (event) => {
      event.preventDefault();
      if (disabled) return;

      const role = event.dataTransfer.getData('application/reactflow');
      if (!role) return;

      const position = screenToFlowPosition({
        x: event.clientX,
        y: event.clientY,
      });

      onDrop(role, position);
    },
    [disabled, screenToFlowPosition, onDrop]
  );

  /**
   * Handle new connections with duplicate/self-loop checks.
   */
  const handleConnect = useCallback(
    (params) => {
      if (disabled) return;

      // Self-loop check
      if (isSelfLoop(params.source, params.target)) {
        if (executionPattern !== 'cyclic') {
          toast.error('Self-loops are only allowed for cyclic workflows.');
          return;
        }
      }

      // Duplicate edge check
      if (isDuplicateEdge(edges, params.source, params.target)) {
        toast.error('Connection already exists between these nodes.');
        return;
      }

      onConnect(params);
    },
    [disabled, edges, executionPattern, onConnect]
  );

  /**
   * Handle node deletion — also remove agent config.
   */
  const handleNodesDelete = useCallback(
    (deletedNodes) => {
      if (disabled) return;
      deletedNodes.forEach((node) => {
        if (onNodeDelete) onNodeDelete(node);
      });
    },
    [disabled, onNodeDelete]
  );

  return (
    <div ref={reactFlowWrapper} className="flex-1 h-full">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        onNodesChange={disabled ? undefined : onNodesChange}
        onEdgesChange={disabled ? undefined : onEdgesChange}
        onConnect={handleConnect}
        onNodeClick={onNodeClick}
        onNodesDelete={handleNodesDelete}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        nodeTypes={nodeTypes}
        defaultEdgeOptions={defaultEdgeOptions}
        fitView
        deleteKeyCode={disabled ? null : 'Delete'}
        selectionKeyCode={disabled ? null : 'Shift'}
        multiSelectionKeyCode={disabled ? null : 'Control'}
        nodesDraggable={!disabled}
        nodesConnectable={!disabled}
        elementsSelectable={!disabled}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant="dots" gap={16} size={1} color="#e2e8f0" />
        <MiniMap
          position="bottom-right"
          nodeColor={(node) => {
            const roleColors = {
              retriever: '#3b82f6',
              analyzer: '#8b5cf6',
              validator: '#22c55e',
              escalator: '#f97316',
              custom: '#6b7280',
            };
            return roleColors[node.data?.role] || '#6b7280';
          }}
          maskColor="rgba(0,0,0,0.08)"
          className="!bg-white !border !border-gray-200 !rounded-lg !shadow-sm"
        />
      </ReactFlow>
    </div>
  );
}
