"""Report service — orchestrate agent workflow and persist results.

NOTE: Now delegates to app.orchestration.report_workflow.
      Kept for backward compatibility with API and task layers.
"""

from __future__ import annotations

from app.agents.graphs.report_graph import report_workflow


def generate_report_sync(project_id: str, user_id: str, week_start: str = "") -> dict:
    """Generate a weekly report (sync wrapper for Celery / CLI).

    Returns:
        {"success": bool, "report_id": str, "title": str, "content": str, "error": str | None}
    """
    return report_workflow.run_and_save(project_id=project_id, user_id=user_id, week_start=week_start)
