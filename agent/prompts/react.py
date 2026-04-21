"""ReAct and task-execution prompts."""

from __future__ import annotations

REACT_PROMPT = """\
Thought: decide the next smallest action.
Action: call a tool or domain capability.
Observation: capture what happened before continuing.
"""

REPORT_PROMPT = """请根据以下信息生成本周项目周报：

## 项目信息
- 项目名称：{project_name}
- 项目编号：{project_code}
- 项目描述：{project_desc}
- 报告周期：{week_start} 至 {week_end}

## 本周进度记录
{progress_text}

## 相关文档内容
{documents_text}

## 历史周报参考
{prev_reports_text}

---

请生成包含以下章节的周报：
1. **周报摘要** — 3-5句话概括本周整体情况
2. **本周工作完成情况** — 详细列出已完成的工作内容
3. **关键指标** — 整体进度百分比、里程碑完成情况
4. **存在问题与风险** — 当前遇到的困难和潜在风险
5. **下周工作计划** — 下周的主要工作安排
6. **需要协调事项** — 需要上级或其他部门协助的事项

请用 Markdown 格式输出完整周报。"""

QUERY_PROMPT = """用户问题：{question}

## 项目信息
- 名称：{project_name}（{project_code}）
- 描述：{project_desc}

## 最近进度记录
{progress_text}

## 相关文档内容
{documents_text}

## 最新进度视频
{video_text}

---

请根据以上信息回答用户的问题。回答要简洁准确，引用具体数据。
如果有视频链接，请在回答中附上，方便用户查看现场情况。"""


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

    return REPORT_PROMPT.format(
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

    return QUERY_PROMPT.format(
        question=question,
        project_name=project_info.get("name", "未知项目"),
        project_code=project_info.get("code", "N/A"),
        project_desc=project_info.get("description", "")[:200],
        progress_text=progress_text,
        documents_text=docs_text,
        video_text=video_text,
    )
