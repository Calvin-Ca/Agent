"""ReAct engine — backward-compatible re-exports.

The actual implementations now live in:
- agent.planning.nodes      — shared workflow nodes and routing functions
- agent.workflows            — QueryWorkflow and ReportWorkflow classes
"""

from __future__ import annotations

from agent.planning.nodes import (
    _extract_summary,
    data_collector_node,
    progress_query_node,
    report_reviewer_node,
    report_writer_node,
    route_after_data_collector,
    route_after_planner,
    route_after_reviewer,
)
from agent.core.state import AgentState, WorkflowState
from agent.planning.planner import ExecutionPlan
from agent.workflows.query_workflow import QueryWorkflow, query_workflow
from agent.workflows.report_workflow import ReportWorkflow, report_workflow


class ReActEngine:
    """Track a lightweight reasoning trace for each plan step."""

    async def run(self, state: AgentState, plan: ExecutionPlan) -> AgentState:
        state.plan = plan.steps
        for step in plan.steps:
            state.add_trace(
                thought=f"Need to {step.description.lower()}",
                action=step.name,
                observation="step scheduled",
            )
        return state


__all__ = [
    "ReActEngine",
    "QueryWorkflow",
    "ReportWorkflow",
    "data_collector_node",
    "progress_query_node",
    "report_writer_node",
    "report_reviewer_node",
    "route_after_planner",
    "route_after_data_collector",
    "route_after_reviewer",
    "query_workflow",
    "report_workflow",
    "_extract_summary",
]
