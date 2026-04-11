"""Prompt templates for the agent workflow.

All prompts use plain f-string formatting (no Jinja2 dependency).
"""

from __future__ import annotations

# ═══════════════════════════════════════════════════════════════
# Report Generation
# ═══════════════════════════════════════════════════════════════

REPORT_SYSTEM = """你是一个专业的工程项目周报撰写助手。你的任务是根据提供的项目数据、进度记录和相关文档内容，生成结构化的项目周报。

要求：
1. 语言简洁专业，适合提交给管理层阅读
2. 数据准确，所有数字和进度百分比必须来自提供的数据
3. 突出本周的关键进展、存在的问题和下周计划
4. 使用 Markdown 格式输出"""

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


def build_report_prompt(
    project_info: dict,
    progress_records: list[dict],
    documents_text: list[str],
    prev_reports: list[dict],
    week_start: str,
    week_end: str,
) -> str:
    """Build the full report generation prompt."""
    # Format progress records
    if progress_records:
        progress_lines = []
        for r in progress_records:
            line = f"- [{r['date']}] 进度:{r['progress']}%"
            if r.get("milestone"):
                line += f" | 里程碑:{r['milestone']}"
            if r.get("description"):
                line += f"\n  {r['description']}"
            if r.get("blockers"):
                line += f"\n  ⚠ 问题:{r['blockers']}"
            if r.get("next_steps"):
                line += f"\n  → 计划:{r['next_steps']}"
            progress_lines.append(line)
        progress_text = "\n".join(progress_lines)
    else:
        progress_text = "（暂无进度记录）"

    # Format document chunks
    if documents_text:
        docs_text = "\n\n".join(
            f"[文档片段 {i+1}]\n{chunk[:500]}"
            for i, chunk in enumerate(documents_text[:10])  # Max 10 chunks
        )
    else:
        docs_text = "（暂无相关文档）"

    # Format previous reports
    if prev_reports:
        prev_text = "\n".join(
            f"- [{r['week_start']}~{r['week_end']}] {r.get('summary', '无摘要')[:200]}"
            for r in prev_reports[:3]
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


# ═══════════════════════════════════════════════════════════════
# Report Review
# ═══════════════════════════════════════════════════════════════

REVIEW_SYSTEM = """你是一个周报质量审核助手。请检查以下周报的质量，并给出修改建议。"""

REVIEW_PROMPT = """请审核以下项目周报，检查：
1. 内容完整性 — 是否包含所有必要章节
2. 数据准确性 — 进度数字是否与原始数据一致
3. 语言规范性 — 是否简洁专业，无口语化表达
4. 逻辑连贯性 — 问题和计划是否对应

## 原始数据摘要
- 项目：{project_name}
- 周期：{week_start} ~ {week_end}
- 最新进度：{latest_progress}%

## 待审核周报
{report_draft}

---

请输出：
1. 总体评分（1-10分）
2. 具体问题列表（如有）
3. 修改建议
4. 如果评分>=7分，输出"APPROVED"；否则输出"NEEDS_REVISION"以及修改后的完整周报。"""


def build_review_prompt(
    report_draft: str,
    project_info: dict,
    week_start: str,
    week_end: str,
    latest_progress: float,
) -> str:
    """Build the review prompt."""
    return REVIEW_PROMPT.format(
        project_name=project_info.get("name", "未知项目"),
        week_start=week_start,
        week_end=week_end,
        latest_progress=latest_progress,
        report_draft=report_draft,
    )


# ═══════════════════════════════════════════════════════════════
# Progress Query
# ═══════════════════════════════════════════════════════════════

QUERY_SYSTEM = """你是一个项目进度查询助手。根据提供的项目数据和文档内容，用中文准确回答用户的问题。
如果数据中没有相关信息，请如实说明，不要编造。"""

QUERY_PROMPT = """用户问题：{question}

## 项目信息
- 名称：{project_name}（{project_code}）
- 描述：{project_desc}

## 最近进度记录
{progress_text}

## 相关文档内容
{documents_text}

---

请根据以上信息回答用户的问题。回答要简洁准确，引用具体数据。"""


def build_query_prompt(
    question: str,
    project_info: dict,
    progress_records: list[dict],
    documents_text: list[str],
) -> str:
    """Build the query prompt."""
    if progress_records:
        progress_text = "\n".join(
            f"- [{r['date']}] 进度:{r['progress']}% | {r.get('description', '')[:100]}"
            for r in progress_records
        )
    else:
        progress_text = "（暂无进度记录）"

    if documents_text:
        docs_text = "\n".join(
            f"[片段{i+1}] {chunk[:300]}"
            for i, chunk in enumerate(documents_text[:5])
        )
    else:
        docs_text = "（暂无相关文档）"

    return QUERY_PROMPT.format(
        question=question,
        project_name=project_info.get("name", "未知项目"),
        project_code=project_info.get("code", "N/A"),
        project_desc=project_info.get("description", "")[:200],
        progress_text=progress_text,
        documents_text=docs_text,
    )