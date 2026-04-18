"""Node: Executor — execute tool calls decided by the planner.

TODO: Implement tool-calling executor node that:
1. Receives a list of tool calls from the planner
2. Executes them via tool_registry
3. Aggregates results back into state
"""

from __future__ import annotations

from app.agents.state import AgentState


def executor_node(state: AgentState) -> AgentState:
    """Execute tool calls. Placeholder for future implementation."""
    raise NotImplementedError("Executor node not yet implemented")
