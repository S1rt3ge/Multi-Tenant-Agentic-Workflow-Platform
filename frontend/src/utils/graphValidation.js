/**
 * Graph validation utilities for the workflow builder.
 * Validates graph structure before execution.
 */

/**
 * Build adjacency list from edges.
 * @param {Array} nodes - React Flow nodes
 * @param {Array} edges - React Flow edges
 * @returns {Map} adjacency list (nodeId -> Set of connected nodeIds)
 */
function buildAdjacencyList(nodes, edges) {
  const adj = new Map();
  nodes.forEach((n) => adj.set(n.id, new Set()));
  edges.forEach((e) => {
    if (adj.has(e.source)) adj.get(e.source).add(e.target);
    if (adj.has(e.target)) adj.get(e.target).add(e.source);
  });
  return adj;
}

/**
 * Check if all nodes are connected (no orphan nodes) using BFS.
 * @param {Array} nodes
 * @param {Array} edges
 * @returns {boolean}
 */
function isFullyConnected(nodes, edges) {
  if (nodes.length <= 1) return true;

  const adj = buildAdjacencyList(nodes, edges);
  const visited = new Set();
  const queue = [nodes[0].id];
  visited.add(nodes[0].id);

  while (queue.length > 0) {
    const current = queue.shift();
    const neighbors = adj.get(current) || new Set();
    for (const neighbor of neighbors) {
      if (!visited.has(neighbor)) {
        visited.add(neighbor);
        queue.push(neighbor);
      }
    }
  }

  return visited.size === nodes.length;
}

/**
 * Detect cycles in a directed graph using DFS.
 * @param {Array} nodes
 * @param {Array} edges
 * @returns {boolean} true if cycle detected
 */
function hasCycle(nodes, edges) {
  const adj = new Map();
  nodes.forEach((n) => adj.set(n.id, []));
  edges.forEach((e) => {
    if (adj.has(e.source)) adj.get(e.source).push(e.target);
  });

  const WHITE = 0;
  const GRAY = 1;
  const BLACK = 2;
  const color = new Map();
  nodes.forEach((n) => color.set(n.id, WHITE));

  function dfs(nodeId) {
    color.set(nodeId, GRAY);
    const neighbors = adj.get(nodeId) || [];
    for (const neighbor of neighbors) {
      if (color.get(neighbor) === GRAY) return true;
      if (color.get(neighbor) === WHITE && dfs(neighbor)) return true;
    }
    color.set(nodeId, BLACK);
    return false;
  }

  for (const node of nodes) {
    if (color.get(node.id) === WHITE) {
      if (dfs(node.id)) return true;
    }
  }

  return false;
}

/**
 * Find orphan nodes (not connected to any edge).
 * @param {Array} nodes
 * @param {Array} edges
 * @returns {Array} orphan node ids
 */
function findOrphanNodes(nodes, edges) {
  if (nodes.length <= 1) return [];

  const connectedIds = new Set();
  edges.forEach((e) => {
    connectedIds.add(e.source);
    connectedIds.add(e.target);
  });

  return nodes
    .filter((n) => !connectedIds.has(n.id))
    .map((n) => n.id);
}

/**
 * Validate graph structure for execution readiness.
 * @param {Array} nodes - React Flow nodes
 * @param {Array} edges - React Flow edges
 * @param {Array} agentConfigs - Agent configs from backend
 * @param {string} executionPattern - 'linear' | 'parallel' | 'cyclic'
 * @returns {{ valid: boolean, errors: string[] }}
 */
export function validateGraph(nodes, edges, agentConfigs, executionPattern) {
  const errors = [];

  // 1. At least 1 node
  if (nodes.length === 0) {
    errors.push('Graph must have at least 1 node.');
    return { valid: false, errors };
  }

  // 2. All nodes connected (no orphans) — only if more than 1 node
  if (nodes.length > 1) {
    const orphans = findOrphanNodes(nodes, edges);
    if (orphans.length > 0) {
      errors.push(
        `Orphan nodes found (not connected): ${orphans.join(', ')}. Connect all nodes with edges.`
      );
    }

    if (!isFullyConnected(nodes, edges)) {
      errors.push(
        'Graph is not fully connected. All nodes must be reachable from any other node.'
      );
    }
  }

  // 3. DAG check for non-cyclic patterns
  if (executionPattern !== 'cyclic' && hasCycle(nodes, edges)) {
    errors.push(
      'Graph contains cycles but workflow pattern is not "cyclic". Remove cycles or change pattern to "cyclic".'
    );
  }

  // 4. Each node has an agent_config
  const configNodeIds = new Set(agentConfigs.map((c) => c.node_id));
  const missingConfig = nodes.filter((n) => !configNodeIds.has(n.id));
  if (missingConfig.length > 0) {
    errors.push(
      `Nodes without agent configuration: ${missingConfig.map((n) => n.data?.label || n.id).join(', ')}. Configure each agent.`
    );
  }

  // 5. Each agent has system_prompt filled
  const emptyPrompt = agentConfigs.filter(
    (c) => !c.system_prompt || c.system_prompt.trim() === ''
  );
  if (emptyPrompt.length > 0) {
    errors.push(
      `Agents without system prompt: ${emptyPrompt.map((c) => c.name).join(', ')}. Fill in system prompts.`
    );
  }

  return { valid: errors.length === 0, errors };
}

/**
 * Check if an edge already exists between two nodes (duplicate check).
 * @param {Array} edges
 * @param {string} source
 * @param {string} target
 * @returns {boolean}
 */
export function isDuplicateEdge(edges, source, target) {
  return edges.some((e) => e.source === source && e.target === target);
}

/**
 * Check if an edge is a self-loop.
 * @param {string} source
 * @param {string} target
 * @returns {boolean}
 */
export function isSelfLoop(source, target) {
  return source === target;
}
