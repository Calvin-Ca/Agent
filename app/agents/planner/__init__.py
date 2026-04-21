"""app.agents.planner — planner module.

Public API
----------
BasePlanner        Abstract base class for custom planner implementations.
DefaultPlanner     Standard implementation used by all built-in workflows.
planner_node       LangGraph-compatible node function (uses DefaultPlanner).

Usage in a LangGraph graph
--------------------------
    from app.agents.planner import planner_node

    graph.add_node("planner", planner_node)

Swapping the planner implementation
------------------------------------
    from app.agents.planner.base import BasePlanner
    from app.agents.callbacks.logging import log_node
    from app.agents.state import AgentState

    class MyPlanner(BasePlanner):
        def plan(self, state: AgentState) -> AgentState:
            ...

    @log_node
    def my_planner_node(state: AgentState) -> AgentState:
        return MyPlanner().plan(state)

    graph.add_node("planner", my_planner_node)
"""

from __future__ import annotations

from app.agents.planner.base import BasePlanner
from app.agents.planner.default_planner import DefaultPlanner
from app.agents.callbacks.logging import log_node
from app.agents.state import AgentState

# ── LangGraph node adapter ────────────────────────────────────────────────

_default_planner = DefaultPlanner()


@log_node
def planner_node(state: AgentState) -> AgentState:
    """LangGraph node — delegates to DefaultPlanner.plan()."""
    return _default_planner.plan(state)


__all__ = [
    "BasePlanner",
    "DefaultPlanner",
    "planner_node",
]
