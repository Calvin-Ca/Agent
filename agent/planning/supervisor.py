"""Supervisor workflow for coordinating multiple specialized agent runs."""

from __future__ import annotations

import time
from typing import Any, Literal

from loguru import logger

from agent.core.state import WorkflowState


class SupervisorState(WorkflowState, total=False):
    """Workflow state for the supervisor flow."""

    sub_tasks: list[dict[str, Any]]
    sub_results: list[dict[str, Any]]
    final_response: str
    delegation_plan: str
    max_delegations: int
    current_delegation: int


def supervisor_planner(state: SupervisorState) -> SupervisorState:
    """Decompose a user request into sub-tasks.

    The current implementation is intentionally conservative and acts as a
    placeholder until task decomposition is implemented.
    """
    logger.info("[Supervisor:Planner] Decomposing request: {}", state.get("user_input", "")[:80])
    return {
        **state,
        "sub_tasks": [],
        "sub_results": [],
        "current_step": "supervisor_planner",
        "current_delegation": 0,
        "max_delegations": state.get("max_delegations", 5),
    }


def supervisor_dispatcher(state: SupervisorState) -> SupervisorState:
    """Dispatch each sub-task to a specialized workflow."""
    logger.info("[Supervisor:Dispatcher] Dispatching {} sub-tasks", len(state.get("sub_tasks", [])))
    return {
        **state,
        "current_step": "supervisor_dispatcher",
    }


def supervisor_aggregator(state: SupervisorState) -> SupervisorState:
    """Aggregate sub-workflow results into a single response."""
    logger.info("[Supervisor:Aggregator] Aggregating {} results", len(state.get("sub_results", [])))
    return {
        **state,
        "final_response": "",
        "current_step": "supervisor_aggregator",
        "done": True,
    }


def route_after_supervisor_planner(state: SupervisorState):
    end = _workflow_end()
    if state.get("error"):
        return end
    if not state.get("sub_tasks"):
        return end
    return "dispatcher"


def route_after_dispatcher(state: SupervisorState):
    end = _workflow_end()
    if state.get("error"):
        return end
    return "aggregator"


class SupervisorWorkflow:
    """Multi-agent supervisor workflow backed by LangGraph when available."""

    def __init__(self) -> None:
        self._compiled = None

    def build(self):
        try:
            from langgraph.graph import END, StateGraph
        except ImportError:
            logger.warning("langgraph not installed, supervisor workflow will use sequential execution")
            return None

        graph = StateGraph(SupervisorState)
        graph.add_node("planner", supervisor_planner)
        graph.add_node("dispatcher", supervisor_dispatcher)
        graph.add_node("aggregator", supervisor_aggregator)
        graph.set_entry_point("planner")
        graph.add_conditional_edges("planner", route_after_supervisor_planner)
        graph.add_conditional_edges("dispatcher", route_after_dispatcher)
        graph.add_edge("aggregator", END)

        self._compiled = graph.compile()
        logger.info("Supervisor workflow compiled")
        return self._compiled

    def _get_graph(self):
        if self._compiled is None:
            self.build()
        return self._compiled

    def run(
        self,
        user_input: str,
        project_id: str,
        user_id: str,
        **kwargs,
    ) -> dict:
        started_at = time.perf_counter()
        logger.info("[Workflow:Supervisor] START | project={} input='{}'", project_id, user_input[:80])

        initial_state: SupervisorState = {
            "task_type": "unknown",
            "project_id": project_id,
            "user_id": user_id,
            "user_input": user_input,
            "week_start": "",
            "project_info": {},
            "progress_records": [],
            "documents_text": [],
            "image_descriptions": [],
            "sql_results": [],
            "latest_video_info": None,
            "report_draft": "",
            "report_title": "",
            "report_summary": "",
            "review_feedback": "",
            "query_answer": "",
            "current_step": "",
            "error": "",
            "retry_count": 0,
            "done": False,
            "sub_tasks": [],
            "sub_results": [],
            "final_response": "",
            "delegation_plan": "",
            "max_delegations": kwargs.get("max_delegations", 5),
            "current_delegation": 0,
        }

        graph = self._get_graph()
        if graph is not None:
            final = graph.invoke(initial_state)
        else:
            final = supervisor_planner(initial_state)
            if final.get("sub_tasks") and not final.get("error"):
                final = supervisor_dispatcher(final)
            if final.get("sub_tasks") and not final.get("error"):
                final = supervisor_aggregator(final)

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        error = final.get("error", "")
        if error:
            logger.error("[Workflow:Supervisor] FAILED {:.0f}ms | error={}", elapsed_ms, error)
            return {"success": False, "response": "", "sub_results": [], "error": error}

        logger.info("[Workflow:Supervisor] DONE {:.0f}ms", elapsed_ms)
        return {
            "success": True,
            "response": final.get("final_response", ""),
            "sub_results": final.get("sub_results", []),
            "error": None,
        }


def _workflow_end():
    try:
        from langgraph.graph import END

        return END
    except ImportError:
        return "end"


supervisor_workflow = SupervisorWorkflow()


__all__ = [
    "SupervisorState",
    "SupervisorWorkflow",
    "route_after_dispatcher",
    "route_after_supervisor_planner",
    "supervisor_aggregator",
    "supervisor_dispatcher",
    "supervisor_planner",
    "supervisor_workflow",
]
