"""
Graph Compiler: converts workflow JSON definition + agent_configs into a
LangGraph StateGraph that can be executed.

Input: workflow.definition (JSONB) = {nodes: [...], edges: [...]}
Output: compiled LangGraph StateGraph

State schema:
    messages: list[dict]       — conversation messages
    current_agent: str         — name of the currently executing agent
    results: dict[str, str]    — {agent_name: output} for each completed step
    metadata: dict             — execution metadata (execution_id, tenant_id, etc.)
"""

import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from langgraph.graph import StateGraph, END

from app.models.agent_config import AgentConfig

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# State type
# ---------------------------------------------------------------------------

class AgentState(dict):
    """Workflow execution state.

    Keys:
        messages: list[dict]
        current_agent: str
        results: dict[str, str]
        metadata: dict
    """
    pass


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

class CompilationError(Exception):
    """Raised when graph compilation fails validation."""
    pass


def validate_definition(definition: dict) -> None:
    """Validate workflow definition before compilation.

    Checks:
    - At least 1 node
    - All edge sources/targets reference existing nodes
    - All nodes are connected (no orphans)
    """
    nodes = definition.get("nodes", [])
    edges = definition.get("edges", [])

    if not nodes:
        raise CompilationError("Workflow has no nodes")

    node_ids = {n.get("id") for n in nodes}

    for edge in edges:
        source = edge.get("source")
        target = edge.get("target")
        if source not in node_ids:
            raise CompilationError(f"Edge references unknown source node: {source}")
        if target not in node_ids:
            raise CompilationError(f"Edge references unknown target node: {target}")

    # Check connectivity (all nodes must be reachable or have at least one edge)
    if len(nodes) > 1 and not edges:
        raise CompilationError("Multiple nodes but no edges — graph is disconnected")

    connected_nodes = set()
    for edge in edges:
        connected_nodes.add(edge.get("source"))
        connected_nodes.add(edge.get("target"))

    if len(nodes) > 1:
        orphans = node_ids - connected_nodes
        if orphans:
            raise CompilationError(f"Orphan nodes not connected to any edge: {orphans}")


# ---------------------------------------------------------------------------
# Compiler
# ---------------------------------------------------------------------------

async def compile_graph(
    definition: dict,
    workflow_id: UUID,
    tenant_id: UUID,
    db: AsyncSession,
) -> tuple[Any, dict[str, AgentConfig]]:
    """Compile a workflow definition into a LangGraph StateGraph.

    Args:
        definition: Workflow definition JSON {nodes, edges}.
        workflow_id: The workflow UUID.
        tenant_id: The tenant UUID.
        db: Database session for loading agent configs.

    Returns:
        Tuple of (compiled_graph, agent_configs_map).
        agent_configs_map: {node_id: AgentConfig} for runtime access.

    Raises:
        CompilationError: If definition is invalid or agent configs are missing.
    """
    validate_definition(definition)

    nodes = definition.get("nodes", [])
    edges = definition.get("edges", [])

    # Load agent configs for all nodes
    node_ids = [n.get("id") for n in nodes]

    result = await db.execute(
        select(AgentConfig).where(
            AgentConfig.workflow_id == workflow_id,
            AgentConfig.tenant_id == tenant_id,
            AgentConfig.node_id.in_(node_ids),
        )
    )
    agent_configs = list(result.scalars().all())
    agent_config_map = {ac.node_id: ac for ac in agent_configs}

    # Verify all nodes have agent configs
    missing = set(node_ids) - set(agent_config_map.keys())
    if missing:
        raise CompilationError(
            f"Agent configs missing for nodes: {missing}. "
            "Configure agents for all nodes before running."
        )

    # Build LangGraph StateGraph
    graph = StateGraph(AgentState)

    # Add nodes
    for node in nodes:
        node_id = node.get("id")
        ac = agent_config_map[node_id]
        # Create a node function that will be replaced at execution time
        # The actual execution uses the agent_config_map
        graph.add_node(node_id, _make_node_function(node_id))

    # Determine entry point (first node with no incoming edges)
    targets = {e.get("target") for e in edges}
    sources = {e.get("source") for e in edges}

    entry_nodes = [n.get("id") for n in nodes if n.get("id") not in targets]
    if not entry_nodes:
        # All nodes have incoming edges — cyclic graph, pick first node
        entry_nodes = [nodes[0].get("id")]

    graph.set_entry_point(entry_nodes[0])

    # Determine terminal nodes (nodes with no outgoing edges)
    terminal_nodes = [n.get("id") for n in nodes if n.get("id") not in sources]

    # Add edges
    # Build adjacency for conditional routing
    adjacency: dict[str, list[dict]] = {}
    for edge in edges:
        source = edge.get("source")
        if source not in adjacency:
            adjacency[source] = []
        adjacency[source].append(edge)

    for source, outgoing_edges in adjacency.items():
        has_conditions = any(
            edge.get("data", {}).get("condition") for edge in outgoing_edges
        )

        if has_conditions:
            # Conditional edges — for cyclic/branching patterns
            condition_map = {}
            for edge in outgoing_edges:
                condition = edge.get("data", {}).get("condition", "default")
                target = edge.get("target")
                condition_map[condition] = target

            # Add a default END if not all conditions lead somewhere
            if "default" not in condition_map:
                condition_map["default"] = END

            graph.add_conditional_edges(
                source,
                _make_condition_function(condition_map),
                condition_map,
            )
        else:
            # Simple edges — single outgoing edge per source
            if len(outgoing_edges) == 1:
                target = outgoing_edges[0].get("target")
                graph.add_edge(source, target)
            else:
                # Multiple non-conditional edges — fan out (pick first for now)
                # In practice, parallel execution would be handled differently
                for edge in outgoing_edges:
                    target = edge.get("target")
                    graph.add_edge(source, target)

    # Add END edges for terminal nodes
    for node_id in terminal_nodes:
        if node_id not in adjacency:
            graph.add_edge(node_id, END)

    # Compile
    compiled = graph.compile()
    return compiled, agent_config_map


def _make_node_function(node_id: str):
    """Create a placeholder node function for the StateGraph.

    The actual agent execution is handled by the executor which
    intercepts each step and runs the agent through the BaseAgent.
    """

    async def node_fn(state: AgentState) -> AgentState:
        # This is a placeholder — the executor patches this at runtime
        # to call execute_agent with the real agent_config
        state["current_agent"] = node_id
        return state

    node_fn.__name__ = f"node_{node_id}"
    return node_fn


def _make_condition_function(condition_map: dict[str, str]):
    """Create a condition function for conditional edges.

    Checks the state for a 'next_action' or 'condition' key
    set by the previous agent to determine routing.
    """

    def condition_fn(state: AgentState) -> str:
        metadata = state.get("metadata", {})
        # Check if the agent set a next_action
        next_action = metadata.get("next_action", "default")
        if next_action in condition_map:
            return next_action
        return "default"

    return condition_fn


def build_edge_adjacency(definition: dict) -> dict[str, list[dict]]:
    """Return source->edges adjacency preserving definition order."""
    adjacency: dict[str, list[dict]] = {}
    for edge in definition.get("edges", []):
        source = edge.get("source")
        if not source:
            continue
        adjacency.setdefault(source, []).append(edge)
    return adjacency
