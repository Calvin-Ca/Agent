"""Weekly report generation workflow backed by LangGraph when available."""

from __future__ import annotations

import time
from datetime import date, timedelta

from loguru import logger

from agent.planning.nodes import (
    data_collector_node,
    report_reviewer_node,
    report_writer_node,
    route_after_data_collector,
    route_after_planner,
    route_after_reviewer,
)
from agent.planning.planner import planner_node
from agent.core.state import WorkflowState
from agent.infra.metrics import record_workflow
from agent.memory.manager import structured_memory


class ReportWorkflow:
    """Weekly report generation workflow backed by LangGraph when available."""

    def __init__(self) -> None:
        self._compiled = None

    def build(self):
        try:
            from langgraph.graph import END, StateGraph
        except ImportError:
            logger.warning("langgraph not installed, report workflow will use sequential execution")
            return None

        graph = StateGraph(WorkflowState)
        graph.add_node("planner", planner_node)
        graph.add_node("data_collector", data_collector_node)
        graph.add_node("report_writer", report_writer_node)
        graph.add_node("report_reviewer", report_reviewer_node)
        graph.set_entry_point("planner")
        graph.add_conditional_edges("planner", route_after_planner)
        graph.add_conditional_edges("data_collector", route_after_data_collector)
        graph.add_edge("report_writer", "report_reviewer")
        graph.add_conditional_edges("report_reviewer", route_after_reviewer)
        self._compiled = graph.compile()
        return self._compiled

    def _get_graph(self):
        if self._compiled is None:
            self.build()
        return self._compiled

    def run(self, project_id: str, user_id: str, week_start: str = "") -> dict:
        started_at = time.perf_counter()
        initial_state: WorkflowState = {
            "task_type": "report",
            "project_id": project_id,
            "user_id": user_id,
            "user_input": "",
            "week_start": week_start,
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
            final_state = planner_node(initial_state)
            final_state = data_collector_node(final_state)
            final_state = report_writer_node(final_state)
            final_state = report_reviewer_node(final_state)

        if final_state.get("error"):
            return {"success": False, "title": "", "content": "", "summary": "", "error": final_state["error"]}

        record_workflow("report", time.perf_counter() - started_at)
        return {
            "success": True,
            "title": final_state.get("report_title", ""),
            "content": final_state.get("report_draft", ""),
            "summary": final_state.get("report_summary", ""),
            "error": None,
        }

    def run_and_save(self, project_id: str, user_id: str, week_start: str = "") -> dict:
        result = self.run(project_id=project_id, user_id=user_id, week_start=week_start)
        if not result["success"]:
            return {"success": False, "report_id": "", "title": "", "content": "", "error": result["error"]}

        if week_start:
            week_start_date = date.fromisoformat(week_start)
        else:
            today = date.today()
            week_start_date = today - timedelta(days=today.weekday())
        week_end_date = week_start_date + timedelta(days=6)

        report_id = structured_memory.save_report(
            project_id=project_id,
            creator_id=user_id,
            title=result["title"],
            week_start=week_start_date,
            week_end=week_end_date,
            content=result["content"],
            summary=result["summary"],
        )
        return {
            "success": True,
            "report_id": report_id,
            "title": result["title"],
            "content": result["content"],
            "error": None,
        }


report_workflow = ReportWorkflow()
