"""ReAct and task-execution prompts — loaded from .j2 templates."""

from __future__ import annotations

from agent.prompts.loader import load, render

REACT_PROMPT = load("react.j2")


def build_report_prompt(
    project_info: dict,
    progress_records: list[dict],
    documents_text: list[str],
    prev_reports: list[dict],
    week_start: str,
    week_end: str,
) -> str:
    """Build the full report-generation prompt."""
    if progress_records:
        progress_lines = []
        for record in progress_records:
            line = f"- [{record['date']}] 进度:{record['progress']}%"
            if record.get("milestone"):
                line += f" | 里程碑:{record['milestone']}"
            if record.get("description"):
                line += f"\n  {record['description']}"
            if record.get("blockers"):
                line += f"\n  问题:{record['blockers']}"
            if record.get("next_steps"):
                line += f"\n  计划:{record['next_steps']}"
            progress_lines.append(line)
        progress_text = "\n".join(progress_lines)
    else:
        progress_text = "（暂无进度记录）"

    if documents_text:
        docs_text = "\n\n".join(
            f"[文档片段 {index + 1}]\n{chunk[:500]}"
            for index, chunk in enumerate(documents_text[:10])
        )
    else:
        docs_text = "（暂无相关文档）"

    if prev_reports:
        prev_text = "\n".join(
            f"- [{report['week_start']}~{report['week_end']}] {report.get('summary', '无摘要')[:200]}"
            for report in prev_reports[:3]
        )
    else:
        prev_text = "（无历史周报）"

    return render(
        "report.j2",
        project_name=project_info.get("name", "未知项目"),
        project_code=project_info.get("code", "N/A"),
        project_desc=project_info.get("description", "")[:300],
        week_start=week_start,
        week_end=week_end,
        progress_text=progress_text,
        documents_text=docs_text,
        prev_reports_text=prev_text,
    )


def build_query_prompt(
    question: str,
    project_info: dict,
    progress_records: list[dict],
    documents_text: list[str],
    latest_video_info: dict | None = None,
) -> str:
    """Build the prompt used for natural-language project queries."""
    if progress_records:
        progress_text = "\n".join(
            f"- [{record['date']}] 进度:{record['progress']}% | {record.get('description', '')[:100]}"
            for record in progress_records
        )
    else:
        progress_text = "（暂无进度记录）"

    if documents_text:
        docs_text = "\n".join(
            f"[片段{index + 1}] {chunk[:300]}"
            for index, chunk in enumerate(documents_text[:5])
        )
    else:
        docs_text = "（暂无相关文档）"

    if latest_video_info:
        video_text = (
            f"- 文件名：{latest_video_info['filename']}\n"
            f"- 拍摄/上传时间：{latest_video_info.get('last_modified', '未知')}\n"
            f"- 文件大小：{latest_video_info['size'] // 1024} KB\n"
            f"- 共 {latest_video_info['total_videos']} 个视频\n"
            f"- 查看链接：{latest_video_info['presigned_url']}"
        )
    else:
        video_text = "（MinIO 中暂无进度视频）"

    return render(
        "query.j2",
        question=question,
        project_name=project_info.get("name", "未知项目"),
        project_code=project_info.get("code", "N/A"),
        project_desc=project_info.get("description", "")[:200],
        progress_text=progress_text,
        documents_text=docs_text,
        video_text=video_text,
    )
