"""Progress service — orchestrate query agent for natural language questions.

NOTE: Now delegates to app.orchestration.query_workflow.
      Kept for backward compatibility with API layer.
"""

from __future__ import annotations

from app.agents.graphs.query_graph import query_workflow


def query_progress_sync(project_id: str, user_id: str, question: str) -> dict:
    """Answer a natural language question about project progress.

    Returns:
        {"success": bool, "answer": str, "error": str | None}
    """
    return query_workflow.run(project_id=project_id, user_id=user_id, question=question)
