"""Shared workflow nodes and routing functions.

These nodes are used by both QueryWorkflow and ReportWorkflow.
"""

from __future__ import annotations

from datetime import date, timedelta

from loguru import logger

from agent.core.state import WorkflowState
from agent.infra.logger import log_node
from agent.llm.local_provider import llm_generate
from agent.memory.manager import memory_manager
from agent.prompts.react import build_query_prompt, build_report_prompt
from agent.prompts.reflection import REVIEW_SYSTEM, build_review_prompt
from agent.prompts.system import QUERY_SYSTEM, REPORT_SYSTEM
from agent.tools.registry import auto_discover_tools, tool_registry


@log_node
def data_collector_node(state: WorkflowState) -> WorkflowState:
    """Collect structured and unstructured context for report/query execution."""
    auto_discover_tools()
    project_id = state["project_id"]
    task_type = state.get("task_type", "report")

    project_info = memory_manager.structured.get_project_info(project_id)
    if not project_info:
        return {**state, "error": f"项目不存在: {project_id}", "done": True}

    progress_records = memory_manager.structured.get_recent_progress(project_id, weeks=4)
    query_text = (
        state.get("user_input", "")
        if task_type == "query"
        else f"{project_info.get('name', '')} 本周工作进度 施工情况"
    )
    documents_text = memory_manager.long_term.search(query=query_text, project_id=project_id, top_k=8)

    prev_reports: list[dict] = []
    latest_video_info = None

    if task_type == "report":
        prev_reports = memory_manager.structured.get_recent_reports(project_id, limit=2)
    else:
        try:
            video_result = tool_registry.execute("minio.get_latest_video")
            if video_result.success:
                latest_video_info = video_result.data
        except Exception as exc:
            logger.warning("Latest video lookup failed: {}", exc)

    return {
        **state,
        "project_info": project_info,
        "progress_records": progress_records,
        "documents_text": documents_text,
        "sql_results": prev_reports,
        "latest_video_info": latest_video_info,
        "current_step": "data_collector",
    }


@log_node
def progress_query_node(state: WorkflowState) -> WorkflowState:
    """Answer a natural-language progress question."""
    user_input = state.get("user_input", "")
    if not user_input:
        return {**state, "error": "缺少查询问题", "done": True}

    prompt = build_query_prompt(
        question=user_input,
        project_info=state.get("project_info", {}),
        progress_records=state.get("progress_records", []),
        documents_text=state.get("documents_text", []),
        latest_video_info=state.get("latest_video_info"),
    )

    try:
        answer = llm_generate(
            prompt=prompt,
            system=QUERY_SYSTEM,
            max_tokens=1024,
            temperature=0.3,
        )
    except Exception as exc:
        return {**state, "error": f"查询失败: {exc}", "done": True}

    return {
        **state,
        "query_answer": answer,
        "current_step": "progress_query",
        "done": True,
    }


@log_node
def report_writer_node(state: WorkflowState) -> WorkflowState:
    """Generate a weekly report draft from collected context."""
    project_info = state.get("project_info", {})
    progress_records = state.get("progress_records", [])
    documents_text = state.get("documents_text", [])
    prev_reports = state.get("sql_results", [])

    week_start = state.get("week_start", "")
    if not week_start:
        today = date.today()
        week_start = (today - timedelta(days=today.weekday())).isoformat()
    week_end = (date.fromisoformat(week_start) + timedelta(days=6)).isoformat()

    report_title = f"{project_info.get('name', '未知项目')} 周报（{week_start} ~ {week_end}）"
    prompt = build_report_prompt(
        project_info=project_info,
        progress_records=progress_records,
        documents_text=documents_text,
        prev_reports=prev_reports,
        week_start=week_start,
        week_end=week_end,
    )

    try:
        report_draft = llm_generate(
            prompt=prompt,
            system=REPORT_SYSTEM,
            max_tokens=2048,
            temperature=0.3,
        )
    except Exception as exc:
        return {**state, "error": f"报告生成失败: {exc}", "done": True}

    if not report_draft.strip():
        return {**state, "error": "LLM 返回空内容", "done": True}

    return {
        **state,
        "report_draft": report_draft,
        "report_title": report_title,
        "week_start": week_start,
        "current_step": "report_writer",
    }


@log_node
def report_reviewer_node(state: WorkflowState) -> WorkflowState:
    """Review the generated report and extract the executive summary."""
    report_draft = state.get("report_draft", "")
    if not report_draft:
        return {**state, "error": "无周报内容可审核", "done": True}

    progress_records = state.get("progress_records", [])
    latest_progress = progress_records[0].get("progress", 0.0) if progress_records else 0.0
    week_start = state.get("week_start", "")
    week_end = (date.fromisoformat(week_start) + timedelta(days=6)).isoformat() if week_start else ""
    retry_count = state.get("retry_count", 0)

    prompt = build_review_prompt(
        report_draft=report_draft,
        project_info=state.get("project_info", {}),
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
    except Exception as exc:
        logger.warning("Review failed, keeping report draft: {}", exc)
        review_result = "APPROVED (review skipped due to error)"

    if "NEEDS_REVISION" in review_result and retry_count < 1:
        revised_start = review_result.find("# ")
        if revised_start > 0:
            return {
                **state,
                "report_draft": review_result[revised_start:],
                "review_feedback": review_result[:revised_start],
                "retry_count": retry_count + 1,
                "current_step": "report_reviewer",
            }

    return {
        **state,
        "report_summary": _extract_summary(report_draft),
        "review_feedback": review_result,
        "current_step": "report_reviewer",
        "done": True,
    }


# ── Routing Functions ──────────────────────────────────────────


def route_after_planner(state: WorkflowState):
    end = _workflow_end()
    if state.get("error"):
        return end
    return "data_collector"


def route_after_data_collector(state: WorkflowState):
    end = _workflow_end()
    if state.get("error"):
        return end
    return "progress_query" if state.get("task_type", "report") == "query" else "report_writer"


def route_after_reviewer(state: WorkflowState):
    end = _workflow_end()
    if state.get("done"):
        return end
    if state.get("retry_count", 0) > 0 and not state.get("done"):
        return "report_writer"
    return end


# ── Helpers ────────────────────────────────────────────────────


def _extract_summary(report: str) -> str:
    lines = report.strip().splitlines()
    in_summary = False
    summary_lines: list[str] = []

    for line in lines:
        lowered = line.lower().strip()
        if any(keyword in lowered for keyword in ("摘要", "概要", "summary", "总结")):
            in_summary = True
            continue
        if in_summary:
            if line.startswith("##") or (line.startswith("**") and "本周" in line):
                break
            if line.strip():
                summary_lines.append(line.strip())
            if len(summary_lines) >= 5:
                break

    if summary_lines:
        return "\n".join(summary_lines)

    content_lines = [
        line.strip() for line in lines if line.strip() and not line.startswith("#") and not line.startswith("---")
    ]
    return "\n".join(content_lines[:3])


def _workflow_end():
    try:
        from langgraph.graph import END

        return END
    except ImportError:
        return "end"
