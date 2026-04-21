"""Reflection and report-review prompts."""

from __future__ import annotations

REFLECTION_PROMPT = """\
Review the last step. Identify failure causes, missing context, and the safest retry.
"""

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
    """Build the prompt used to review report quality."""
    return REVIEW_PROMPT.format(
        project_name=project_info.get("name", "未知项目"),
        week_start=week_start,
        week_end=week_end,
        latest_progress=latest_progress,
        report_draft=report_draft,
    )
