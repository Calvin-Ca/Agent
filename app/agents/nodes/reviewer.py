"""Node: Report Reviewer — self-check the generated report quality."""

from __future__ import annotations

from loguru import logger

from app.agents.state import AgentState
from app.agents.callbacks.logging import log_node
from app.agents.prompts.templates import REVIEW_SYSTEM, build_review_prompt
from app.model_service.llm import llm_generate


@log_node
def report_reviewer_node(state: AgentState) -> AgentState:
    """Review the report draft and extract summary.

    If review score < 7, the feedback contains a revised version.
    We allow max 1 revision to avoid infinite loops.
    """
    report_draft = state.get("report_draft", "")
    project_info = state.get("project_info", {})
    progress_records = state.get("progress_records", [])
    retry_count = state.get("retry_count", 0)

    if not report_draft:
        return {**state, "error": "无周报内容可审核", "done": True}

    # Get latest progress percentage
    latest_progress = 0.0
    if progress_records:
        latest_progress = progress_records[0].get("progress", 0.0)

    week_start = state.get("week_start", "")
    week_end = ""
    if week_start:
        from datetime import date, timedelta
        week_end = (date.fromisoformat(week_start) + timedelta(days=6)).isoformat()

    logger.info("ReportReviewer: reviewing draft ({} chars, attempt {})", len(report_draft), retry_count + 1)

    prompt = build_review_prompt(
        report_draft=report_draft,
        project_info=project_info,
        week_start=week_start,
        week_end=week_end,
        latest_progress=latest_progress,
    )

    try:
        review_result = llm_generate(
            prompt=prompt,
            system=REVIEW_SYSTEM,
            max_tokens=2048,
            temperature=0.2,
        )
    except Exception as e:
        logger.warning("Review failed (non-fatal, keeping draft): {}", e)
        review_result = "APPROVED (review skipped due to error)"

    # Parse review result
    if "NEEDS_REVISION" in review_result and retry_count < 1:
        # Extract revised report if present
        revised_start = review_result.find("# ")
        if revised_start > 0:
            revised_report = review_result[revised_start:]
            logger.info("ReportReviewer: revision applied ({} chars)", len(revised_report))
            return {
                **state,
                "report_draft": revised_report,
                "review_feedback": review_result[:revised_start],
                "retry_count": retry_count + 1,
                "current_step": "report_reviewer",
            }

    # Extract summary (first 3-5 sentences of the report)
    summary = _extract_summary(report_draft)

    logger.info("ReportReviewer: APPROVED")
    return {
        **state,
        "report_summary": summary,
        "review_feedback": review_result,
        "current_step": "report_reviewer",
        "done": True,
    }


def _extract_summary(report: str) -> str:
    """Extract executive summary from report content."""
    lines = report.strip().splitlines()

    # Try to find the summary section
    in_summary = False
    summary_lines = []

    for line in lines:
        lower = line.lower().strip()
        if any(kw in lower for kw in ("摘要", "概要", "summary", "总结")):
            in_summary = True
            continue
        if in_summary:
            if line.startswith("##") or line.startswith("**") and "本周" in line:
                break  # Next section started
            if line.strip():
                summary_lines.append(line.strip())
            if len(summary_lines) >= 5:
                break

    if summary_lines:
        return "\n".join(summary_lines)

    # Fallback: first 3 non-empty, non-heading lines
    content_lines = [
        l.strip() for l in lines
        if l.strip() and not l.startswith("#") and not l.startswith("---")
    ]
    return "\n".join(content_lines[:3])