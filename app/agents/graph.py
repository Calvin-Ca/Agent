"""LangGraph workflow — the main agent orchestration.

Two workflows:
1. Report: planner → data_collector → report_writer → report_reviewer
2. Query:  planner → data_collector → progress_query

Usage:
    from app.agents.graph import run_report_agent, run_query_agent

    # Generate a weekly report
    result = run_report_agent(project_id="xxx", user_id="yyy")

    # Answer a progress question
    result = run_query_agent(
        project_id="xxx",
        user_id="yyy",
        question="目前整体进度如何？",
    )
"""

from __future__ import annotations

from langgraph.graph import StateGraph, END

from loguru import logger

from app.agents.state import AgentState
from app.agents.nodes.planner import planner_node
from app.agents.nodes.data_collector import data_collector_node
from app.agents.nodes.report_writer import report_writer_node
from app.agents.nodes.report_reviewer import report_reviewer_node
from app.agents.nodes.progress_query import progress_query_node


def _route_after_planner(state: AgentState) -> str:
    """Route based on task_type after planner."""
    if state.get("error"):
        return END
    return "data_collector"


def _route_after_data_collector(state: AgentState) -> str:
    """Route to report_writer or progress_query based on task_type."""
    if state.get("error"):
        return END
    task_type = state.get("task_type", "report")
    if task_type == "query":
        return "progress_query"
    return "report_writer"


def _route_after_reviewer(state: AgentState) -> str:
    """After review, check if revision is needed."""
    if state.get("done"):
        return END
    # Needs revision — go back to writer
    retry_count = state.get("retry_count", 0)
    if retry_count > 0 and not state.get("done"):
        return "report_writer"
    return END


def build_graph() -> StateGraph:
    """Build the LangGraph workflow."""
    graph = StateGraph(AgentState)

    # Add nodes
    graph.add_node("planner", planner_node)
    graph.add_node("data_collector", data_collector_node)
    graph.add_node("report_writer", report_writer_node)
    graph.add_node("report_reviewer", report_reviewer_node)
    graph.add_node("progress_query", progress_query_node)

    # Set entry point
    graph.set_entry_point("planner")

    # Add edges
    graph.add_conditional_edges("planner", _route_after_planner)
    graph.add_conditional_edges("data_collector", _route_after_data_collector)
    graph.add_edge("report_writer", "report_reviewer")
    graph.add_conditional_edges("report_reviewer", _route_after_reviewer)
    graph.add_edge("progress_query", END)

    return graph


# Compile once, reuse
_compiled_graph = None


def get_graph():
    """Get the compiled graph (singleton)."""
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph().compile()
        logger.info("Agent graph compiled")
    return _compiled_graph


# ═══════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════


def run_report_agent(
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
    logger.info("run_report_agent: project={}, user={}", project_id, user_id)

    graph = get_graph()
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
        logger.error("Report agent failed: {}", error)
        return {"success": False, "title": "", "content": "", "summary": "", "error": error}

    return {
        "success": True,
        "title": final_state.get("report_title", ""),
        "content": final_state.get("report_draft", ""),
        "summary": final_state.get("report_summary", ""),
        "error": None,
    }


def run_query_agent(
    project_id: str,
    user_id: str,
    question: str,
) -> dict:
    """Answer a natural language question about project progress.

    Returns:
        {"success": bool, "answer": str, "error": str | None}
    """
    logger.info("run_query_agent: project={}, question='{}'", project_id, question[:50])

    graph = get_graph()
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
        logger.error("Query agent failed: {}", error)
        return {"success": False, "answer": "", "error": error}

    return {
        "success": True,
        "answer": final_state.get("query_answer", ""),
        "error": None,
    }