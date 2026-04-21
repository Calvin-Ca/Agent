"""Node: Report Writer — generate the weekly report via LLM."""

from __future__ import annotations

from datetime import date, timedelta

from loguru import logger

from app.agents.state import AgentState
from app.agents.callbacks.logging import log_node
from app.agents.prompts.templates import REPORT_SYSTEM, build_report_prompt
from app.model_service.llm import llm_generate


@log_node
def report_writer_node(state: AgentState) -> AgentState:
    """Generate a weekly report based on collected data."""
    project_info = state.get("project_info", {})
    progress_records = state.get("progress_records", [])
    documents_text = state.get("documents_text", [])
    prev_reports = state.get("sql_results", [])

    # Determine report week
    week_start_str = state.get("week_start", "")
    if week_start_str:
        week_start = week_start_str
    else:
        today = date.today()
        monday = today - timedelta(days=today.weekday())
        week_start = monday.isoformat()

    week_end_date = date.fromisoformat(week_start) + timedelta(days=6)
    week_end = week_end_date.isoformat()

    # Build title
    project_name = project_info.get("name", "未知项目")
    report_title = f"{project_name} 周报（{week_start} ~ {week_end}）"

    logger.info("ReportWriter: generating '{}'", report_title)

    # Build prompt
    prompt = build_report_prompt(
        project_info=project_info,
        progress_records=progress_records,
        documents_text=documents_text,
        prev_reports=prev_reports,
        week_start=week_start,
        week_end=week_end,
    )

    # Generate via LLM
    try:
        report_draft = llm_generate(
            prompt=prompt,
            system=REPORT_SYSTEM,
            max_tokens=2048,
            temperature=0.3,  # Lower temperature for factual report
        )
    except Exception as e:
        logger.error("LLM generation failed: {}", e)
        return {**state, "error": f"报告生成失败: {e}", "done": True}

    if not report_draft.strip():
        return {**state, "error": "LLM 返回空内容", "done": True}

    logger.info("ReportWriter: generated {} chars", len(report_draft))

    return {
        **state,
        "report_draft": report_draft,
        "report_title": report_title,
        "week_start": week_start,
        "current_step": "report_writer",
    }
