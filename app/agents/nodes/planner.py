"""Thin adapter — re-exports planner_node from app.agents.planner.

All graph modules import from this path:
    from app.agents.nodes.planner import planner_node

The actual implementation lives in app/agents/planner/.
"""

from app.agents.planner import planner_node  # noqa: F401
