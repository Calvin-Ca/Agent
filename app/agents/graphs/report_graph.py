"""Report generation graph — LangGraph state machine.

Flow: planner → data_collector → report_writer → reviewer → END

Usage:
    from app.agents.graphs.report_graph import report_workflow

    result = report_workflow.run(project_id="xxx", user_id="yyy")
"""

from __future__ import annotations

from datetime import date, timedelta

from langgraph.graph import StateGraph, END
from loguru import logger

from app.agents.state import AgentState
from app.agents.nodes.planner import planner_node
from app.agents.nodes.data_collector import data_collector_node
from app.agents.nodes.report_writer import report_writer_node
from app.agents.nodes.reviewer import report_reviewer_node
from app.agents.graphs.edges import (
    route_after_planner,
    route_after_data_collector,
    route_after_reviewer,
)
from app.memory.structured import structured_memory


class ReportWorkflow:
    """Report generation workflow backed by LangGraph."""

    def __init__(self):
        self._compiled = None

    def build(self):
        """Build and compile the LangGraph state machine."""
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("planner", planner_node)
        graph.add_node("data_collector", data_collector_node)
        graph.add_node("report_writer", report_writer_node)
        graph.add_node("report_reviewer", report_reviewer_node)

        # Set entry point
        graph.set_entry_point("planner")

        # Add edges
        graph.add_conditional_edges("planner", route_after_planner)
        graph.add_conditional_edges("data_collector", route_after_data_collector)
        graph.add_edge("report_writer", "report_reviewer")
        graph.add_conditional_edges("report_reviewer", route_after_reviewer)

        self._compiled = graph.compile()
        logger.info("Report workflow compiled")
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
        week_start: str = "",
    ) -> dict:
        """Generate a weekly report.

        Returns:
            {
                "success": bool,
                "title": str,
                "content": str (Markdown),
                "summary": str,
                "error": str | None,
            }
        """
        logger.info("ReportWorkflow.run: project={}, user={}", project_id, user_id)

        graph = self._get_graph()
        initial_state: AgentState = {
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

        error = final_state.get("error", "")
        if error:
            logger.error("Report workflow failed: {}", error)
            return {"success": False, "title": "", "content": "", "summary": "", "error": error}

        return {
            "success": True,
            "title": final_state.get("report_title", ""),
            "content": final_state.get("report_draft", ""),
            "summary": final_state.get("report_summary", ""),
            "error": None,
        }

    def run_and_save(
        self,
        project_id: str,
        user_id: str,
        week_start: str = "",
    ) -> dict:
        """Generate a weekly report and save to database.

        Returns:
            {"success": bool, "report_id": str, "title": str, "content": str, "error": str | None}
        """
        result = self.run(project_id=project_id, user_id=user_id, week_start=week_start)

        if not result["success"]:
            return {"success": False, "report_id": "", "title": "", "content": "", "error": result["error"]}

        # Determine week dates
        if week_start:
            ws = date.fromisoformat(week_start)
        else:
            today = date.today()
            ws = today - timedelta(days=today.weekday())
        we = ws + timedelta(days=6)

        # Save to DB via memory layer
        report_id = structured_memory.save_report(
            project_id=project_id,
            creator_id=user_id,
            title=result["title"],
            week_start=ws,
            week_end=we,
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


# Singleton
report_workflow = ReportWorkflow()
