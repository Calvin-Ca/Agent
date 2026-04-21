"""Prompt templates for the agent workflow.

All system prompts and user prompt templates are collected here for
centralized management.  Each group follows the same pattern:

    XXX_SYSTEM  — system-role prompt (sets LLM persona / constraints)
    XXX_PROMPT  — user-role template (with {placeholder} slots)
    build_xxx_prompt()  — helper that fills in the template

All prompts use plain f-string formatting (no Jinja2 dependency).
"""

from __future__ import annotations

# ═══════════════════════════════════════════════════════════════
# Intent Recognition（意图识别）
# ═══════════════════════════════════════════════════════════════

INTENT_SYSTEM = """你是一个意图识别助手。根据用户输入，识别用户意图并提取参数。

支持的意图（intent）及所需参数：
1. create_project — 创建项目。参数：name(必填), code(可选), description(可选)
2. list_projects — 列出用户的所有项目。无额外参数。
3. update_project — 更新项目信息。参数：project_name(用户提到的项目名称), name(新名称,可选), description(可选), status(可选,0=进行中,1=暂停,2=已关闭)
4. delete_project — 删除项目。参数：project_name(用户提到的项目名称)
5. record_progress — 记录项目进度。参数：project_name(用户提到的项目名称), overall_progress(百分比数字), milestone(可选), description(可选), blockers(可选), next_steps(可选)
6. list_progress — 查看项目进度列表。参数：project_name(用户提到的项目名称)
7. generate_report — 生成项目周报。参数：project_name(用户提到的项目名称), week_start(可选,ISO日期)
8. list_reports — 查看周报列表。参数：project_name(可选,筛选条件)
9. get_report — 查看某份周报的详情。参数：report_id
10. export_report — 导出周报为文件。参数：report_id, format(可选: docx/md，默认docx)
11. query — 自然语言提问，关于项目进度/文档的问答。参数：project_name(用户提到的项目名称), question(用户原始问题)
12. upload_file — 上传文件到项目。参数：project_name(用户提到的项目名称)

参数提取规则：
- project_name：从用户输入中提取项目名称，保留用户原始表述（如"城南花园三期"、"滨江大道"）。
  如果用户没有提到具体项目名称，则不填此参数。

判断规则：
- 如果用户明确要求创建、新建、添加项目 → create_project
- 如果用户要查看、列出、有哪些项目 → list_projects
- 如果用户要修改、更新、变更项目名称/描述/状态 → update_project
- 如果用户要删除、移除项目 → delete_project
- 如果用户要记录、更新进度、汇报进展 → record_progress
- 如果用户要查看、列出进度记录 → list_progress
- 如果用户要生成、撰写、写周报/报告 → generate_report
- 如果用户要查看周报列表 → list_reports
- 如果用户要看某份周报内容 → get_report
- 如果用户要导出、下载周报 → export_report
- 如果用户提出关于项目的问题（如进度如何、有什么问题等）→ query
- 如果无法明确判断但有问题意图 → query

只以JSON 格式回复以下内容，不要输出任何其他内容：
{"intent": "意图名称", "params": {"参数名": "参数值"}}"""

INTENT_PROMPT = """用户输入：{user_input}
是否附带文件：{has_file}

请识别意图并提取参数。注意：请从用户输入中提取项目名称（project_name），而非项目ID。"""


def build_intent_prompt(user_input: str, has_file: bool) -> str:
    """Build the intent recognition prompt."""
    return INTENT_PROMPT.format(
        user_input=user_input,
        has_file="是" if has_file else "否",
    )


# ═══════════════════════════════════════════════════════════════
# Report Generation（周报生成）
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

## 最新进度视频
{video_text}

---

请根据以上信息回答用户的问题。回答要简洁准确，引用具体数据。
如果有视频链接，请在回答中附上，方便用户查看现场情况。"""


def build_query_prompt(
    question: str,
    project_info: dict,
    progress_records: list[dict],
    documents_text: list[str],
    latest_video_info: dict | None = None,
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
