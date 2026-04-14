"""Progress service — orchestrate query agent for natural language questions."""

from __future__ import annotations

from loguru import logger


def query_progress_sync(project_id: str, user_id: str, question: str) -> dict:
    """Answer a natural language question about project progress.

    Returns:
        {"success": bool, "answer": str, "error": str | None}
    """
    from app.agents.graph import run_query_agent

    result = run_query_agent(project_id=project_id, user_id=user_id, question=question)

    if not result["success"]:
        logger.warning("Query failed: {}", result["error"])

    return result