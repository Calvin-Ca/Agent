"""Router graph — the top-level supervisor that recognizes user intent and
dispatches to the appropriate sub-graph (report, query, CRUD, etc.).

This is the entry point for the unified chat endpoint.  It uses LLM-based
intent recognition with a keyword fallback.

Supported intents:
  - create_project / list_projects / update_project / delete_project
  - record_progress / list_progress
  - generate_report / list_reports / get_report / export_report
  - query: 自然语言问答（RAG）
  - upload_file: 上传文件（有附件时自动识别）
"""

from __future__ import annotations

import json
import re

from loguru import logger

from app.model_service.llm import llm_generate

INTENT_SYSTEM = """你是一个意图识别助手。根据用户输入，识别用户意图并提取参数。

支持的意图（intent）及所需参数：
1. create_project — 创建项目。参数：name(必填), code(可选), description(可选)
2. list_projects — 列出用户的所有项目。无额外参数。
3. update_project — 更新项目信息。参数：project_id(可从上下文获取), name(可选), description(可选), status(可选,0=进行中,1=暂停,2=已关闭)
4. delete_project — 删除项目。参数：project_id(可从上下文获取)
5. record_progress — 记录项目进度。参数：project_id(可从上下文获取), overall_progress(百分比数字), milestone(可选), description(可选), blockers(可选), next_steps(可选)
6. list_progress — 查看项目进度列表。参数：project_id(可从上下文获取)
7. generate_report — 生成项目周报。参数：project_id(可从上下文获取), week_start(可选,ISO日期)
8. list_reports — 查看周报列表。参数：project_id(可选,筛选条件)
9. get_report — 查看某份周报的详情。参数：report_id
10. export_report — 导出周报为文件。参数：report_id, format(可选: docx/md，默认docx)
11. query — 自然语言提问，关于项目进度/文档的问答。参数：project_id(可从上下文获取), question(用户原始问题)
12. upload_file — 上传文件到项目。参数：project_id(可从上下文获取)

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

请严格以 JSON 格式回复，不要输出任何其他内容：
{"intent": "意图名称", "params": {"参数名": "参数值"}}"""

INTENT_PROMPT = """用户输入：{user_input}
当前项目ID：{project_id}
是否附带文件：{has_file}

请识别意图并提取参数。"""


def recognize_intent(
    user_input: str,
    project_id: str | None = None,
    has_file: bool = False,
) -> dict:
    """Use LLM to recognize user intent and extract parameters.

    Returns:
        {"intent": str, "params": dict}
    """
    # If file is attached and no other clear intent, default to upload
    if has_file and not any(kw in user_input for kw in ("生成", "周报", "报告", "创建", "删除", "查看", "列出", "进度", "导出")):
        return {"intent": "upload_file", "params": {"project_id": project_id}}

    prompt = INTENT_PROMPT.format(
        user_input=user_input,
        project_id=project_id or "未指定",
        has_file="是" if has_file else "否",
    )

    try:
        raw = llm_generate(prompt=prompt, system=INTENT_SYSTEM, max_tokens=256, temperature=0.1)
        result = _parse_json(raw)
        logger.info("Intent recognized: {} params={}", result.get("intent"), result.get("params"))
        return result
    except Exception as e:
        logger.error("Intent recognition failed: {}", e)
        # Fallback: use keyword matching
        return _keyword_fallback(user_input, project_id, has_file)


def _parse_json(raw: str) -> dict:
    """Extract JSON from LLM output, tolerating markdown fences."""
    # Strip markdown code fences
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`")

    # Try direct parse
    try:
        result = json.loads(cleaned)
        if "intent" in result:
            result.setdefault("params", {})
            return result
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in text
    match = re.search(r"\{[^{}]*\"intent\"[^{}]*\}", cleaned, re.DOTALL)
    if match:
        try:
            result = json.loads(match.group())
            result.setdefault("params", {})
            return result
        except json.JSONDecodeError:
            pass

    raise ValueError(f"无法从 LLM 输出中解析意图: {raw[:200]}")


def _keyword_fallback(user_input: str, project_id: str | None, has_file: bool) -> dict:
    """Simple keyword-based fallback when LLM fails."""
    text = user_input.lower()

    if has_file:
        return {"intent": "upload_file", "params": {"project_id": project_id}}

    if any(kw in text for kw in ("创建项目", "新建项目", "添加项目")):
        return {"intent": "create_project", "params": {}}

    if any(kw in text for kw in ("项目列表", "有哪些项目", "列出项目", "查看项目", "我的项目")):
        return {"intent": "list_projects", "params": {}}

    if any(kw in text for kw in ("删除项目", "移除项目")):
        return {"intent": "delete_project", "params": {"project_id": project_id}}

    if any(kw in text for kw in ("修改项目", "更新项目", "变更项目")):
        return {"intent": "update_project", "params": {"project_id": project_id}}

    if any(kw in text for kw in ("记录进度", "汇报进度", "更新进度", "进度记录")):
        return {"intent": "record_progress", "params": {"project_id": project_id}}

    if any(kw in text for kw in ("进度列表", "查看进度", "进度情况")):
        return {"intent": "list_progress", "params": {"project_id": project_id}}

    if any(kw in text for kw in ("生成周报", "写周报", "撰写周报", "生成报告", "写报告")):
        return {"intent": "generate_report", "params": {"project_id": project_id}}

    if any(kw in text for kw in ("周报列表", "查看周报", "有哪些周报")):
        return {"intent": "list_reports", "params": {"project_id": project_id}}

    if any(kw in text for kw in ("导出周报", "下载周报", "导出报告")):
        return {"intent": "export_report", "params": {}}

    # Default to query
    return {"intent": "query", "params": {"project_id": project_id, "question": user_input}}
