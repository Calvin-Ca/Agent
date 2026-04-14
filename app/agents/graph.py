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

NOTE: This module now delegates to app.orchestration.* for backward compatibility.
"""

from __future__ import annotations

from app.orchestration.report_workflow import report_workflow
from app.orchestration.query_workflow import query_workflow


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
    return report_workflow.run(project_id=project_id, user_id=user_id, week_start=week_start)


def run_query_agent(
    project_id: str,
    user_id: str,
    question: str,
) -> dict:
    """Answer a natural language question about project progress.

    Returns:
        {"success": bool, "answer": str, "error": str | None}
    """
    return query_workflow.run(project_id=project_id, user_id=user_id, question=question)
