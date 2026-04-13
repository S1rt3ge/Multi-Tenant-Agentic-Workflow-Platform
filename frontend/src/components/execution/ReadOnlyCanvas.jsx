import ReactFlow, { Background, MiniMap, Controls } from 'reactflow';
import 'reactflow/dist/style.css';
import AgentNode from '../builder/AgentNode';

/**
 * Custom node types — reuse AgentNode from builder.
 */
const nodeTypes = { agent: AgentNode };

const defaultEdgeOptions = {
  animated: true,
  style: { stroke: '#94a3b8', strokeWidth: 2 },
};

/**
 * ReadOnlyCanvas — displays the workflow graph in read-only mode.
 * Highlights the currently active node during execution.
 *
 * @param {object} props
 * @param {Array} props.nodes - Canvas nodes
 * @param {Array} props.edges - Canvas edges
 * @param {string|null} props.activeNodeId - Currently executing node ID
 */
export default function ReadOnlyCanvas({ nodes, edges, activeNodeId }) {
  // Add highlight styling to the active node
  const styledNodes = nodes.map((node) => {
    if (node.id === activeNodeId) {
      return {
        ...node,
        style: {
          ...node.style,
          boxShadow: '0 0 0 3px #3b82f6, 0 0 20px rgba(59, 130, 246, 0.3)',
          borderRadius: '8px',
        },
      };
    }
    return node;
  });

  // Highlight edges to/from active node
  const styledEdges = edges.map((edge) => {
    if (edge.source === activeNodeId || edge.target === activeNodeId) {
      return {
        ...edge,
        animated: true,
        style: { stroke: '#3b82f6', strokeWidth: 3 },
      };
    }
    return edge;
  });

  return (
    <ReactFlow
      nodes={styledNodes}
      edges={styledEdges}
      nodeTypes={nodeTypes}
      defaultEdgeOptions={defaultEdgeOptions}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      panOnDrag={true}
      zoomOnScroll={true}
      fitView
      fitViewOptions={{ padding: 0.3 }}
      className="bg-gray-50"
    >
      <Background color="#e2e8f0" gap={20} size={1} />
      <MiniMap
        nodeStrokeColor={(n) => (n.id === activeNodeId ? '#3b82f6' : '#94a3b8')}
        nodeColor={(n) => (n.id === activeNodeId ? '#dbeafe' : '#fff')}
        maskColor="rgba(0, 0, 0, 0.05)"
      />
      <Controls showInteractive={false} />
    </ReactFlow>
  );
}
