"""Natural-language query workflow backed by LangGraph when available."""

from __future__ import annotations

import time

from loguru import logger

from agent.core.nodes import data_collector_node, progress_query_node, route_after_data_collector, route_after_planner
from agent.core.planner import planner_node
from agent.core.state import WorkflowState
from agent.infra.metrics import record_workflow


class QueryWorkflow:
    """Natural-language query workflow backed by LangGraph when available."""

    def __init__(self) -> None:
        self._compiled = None

    def build(self):
        try:
            from langgraph.graph import END, StateGraph
        except ImportError:
            logger.warning("langgraph not installed, query workflow will use sequential execution")
            return None

        graph = StateGraph(WorkflowState)
        graph.add_node("planner", planner_node)
        graph.add_node("data_collector", data_collector_node)
        graph.add_node("progress_query", progress_query_node)
        graph.set_entry_point("planner")
        graph.add_conditional_edges("planner", route_after_planner)
        graph.add_conditional_edges("data_collector", route_after_data_collector)
        graph.add_edge("progress_query", END)
        self._compiled = graph.compile()
        return self._compiled

    def _get_graph(self):
        if self._compiled is None:
            self.build()
        return self._compiled

    def run(self, project_id: str, user_id: str, question: str) -> dict:
        started_at = time.perf_counter()
        initial_state: WorkflowState = {
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

        graph = self._get_graph()
        if graph is not None:
            final_state = graph.invoke(initial_state)
        else:
            final_state = progress_query_node(data_collector_node(planner_node(initial_state)))

        if final_state.get("error"):
            return {"success": False, "answer": "", "error": final_state["error"]}

        record_workflow("query", time.perf_counter() - started_at)
        return {"success": True, "answer": final_state.get("query_answer", ""), "error": None}


query_workflow = QueryWorkflow()
