"""Node: Planner — determines task type and routes the workflow.

This module re-exports from app.agents.planner.default_planner
for backward compatibility.
"""

from app.agents.planner.default_planner import planner_node  # noqa: F401
