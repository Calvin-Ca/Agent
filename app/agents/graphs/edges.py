"""Routing functions for LangGraph conditional edges.

Determines the next node based on current state.
Shared across all workflows.
"""

from __future__ import annotations

from langgraph.graph import END

from app.agents.state import AgentState


def route_after_planner(state: AgentState) -> str:
    """Route based on task_type after planner."""
    if state.get("error"):
        return END
    return "data_collector"


def route_after_data_collector(state: AgentState) -> str:
    """Route to report_writer or progress_query based on task_type."""
    if state.get("error"):
        return END
    task_type = state.get("task_type", "report")
    if task_type == "query":
        return "progress_query"
    return "report_writer"


def route_after_reviewer(state: AgentState) -> str:
    """After review, check if revision is needed."""
    if state.get("done"):
        return END
    # Needs revision — go back to writer
    retry_count = state.get("retry_count", 0)
    if retry_count > 0 and not state.get("done"):
        return "report_writer"
    return END
