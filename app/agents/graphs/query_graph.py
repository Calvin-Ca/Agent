"""Natural language query graph — LangGraph state machine.

Flow: planner → data_collector → progress_query → END

Usage:
    from app.agents.graphs.query_graph import query_workflow

    result = query_workflow.run(project_id="xxx", user_id="yyy", question="进度如何？")
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END
from loguru import logger

from app.agents.state import AgentState
from app.agents.nodes.planner import planner_node
from app.agents.nodes.data_collector import data_collector_node
from app.agents.nodes.progress_query import progress_query_node
from app.agents.graphs.edges import route_after_planner, route_after_data_collector


class QueryWorkflow:
    """Natural language query workflow backed by LangGraph."""

    def __init__(self):
        self._compiled = None

    def build(self):
        """Build and compile the LangGraph state machine."""
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("planner", planner_node)
        graph.add_node("data_collector", data_collector_node)
        graph.add_node("progress_query", progress_query_node)

        # Set entry point
        graph.set_entry_point("planner")

        # Add edges
        graph.add_conditional_edges("planner", route_after_planner)
        graph.add_conditional_edges("data_collector", route_after_data_collector)
        graph.add_edge("progress_query", END)

        self._compiled = graph.compile()
        logger.info("Query workflow compiled")
        return self._compiled

    def _get_graph(self):
        """Get the compiled graph (lazy init)."""
        if self._compiled is None:
            self.build()
        return self._compiled

    def run(
        self,
        project_id: str,
        user_id: str,
        question: str,
    ) -> dict:
        """Answer a natural language question about project progress.

        Returns:
            {"success": bool, "answer": str, "error": str | None}
        """
        import time as _time
        workflow_start = _time.perf_counter()
        logger.info("[Workflow:Query] START | project={} question='{}'", project_id, question[:80])

        graph = self._get_graph()
        initial_state: AgentState = {
            "task_type": "query",
            "project_id": project_id,
            "user_id": user_id,
            "user_input": question,
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
        }

        final_state = graph.invoke(initial_state)

        elapsed_ms = (_time.perf_counter() - workflow_start) * 1000
        error = final_state.get("error", "")
        if error:
            logger.error("[Workflow:Query] FAILED | {:.0f}ms | error={}", elapsed_ms, error)
            return {"success": False, "answer": "", "error": error}

        answer = final_state.get("query_answer", "")
        logger.info("[Workflow:Query] DONE | {:.0f}ms | answer_chars={}", elapsed_ms, len(answer))
        return {
            "success": True,
            "answer": answer,
            "error": None,
        }


# Singleton
query_workflow = QueryWorkflow()
