"""Reflection and report-review prompts — loaded from .j2 templates."""

from __future__ import annotations

from agent.prompts.loader import load, render

REFLECTION_PROMPT = load("reflection.j2")
REVIEW_SYSTEM = load("review_system.j2")


def build_review_prompt(
    report_draft: str,
    project_info: dict,
    week_start: str,
    week_end: str,
    latest_progress: float,
) -> str:
    """Build the prompt used to review report quality."""
    return render(
        "review.j2",
        project_name=project_info.get("name", "未知项目"),
        week_start=week_start,
        week_end=week_end,
        latest_progress=latest_progress,
        report_draft=report_draft,
    )
