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
from app.agents.prompts.templates import INTENT_SYSTEM, build_intent_prompt


def recognize_intent(
    user_input: str,
    has_file: bool = False,
) -> dict:
    """Use LLM to recognize user intent and extract parameters.

    Returns:
        {"intent": str, "params": dict}
        params may contain "project_name" (extracted from user input).
    """
    # If file is attached and no other clear intent, default to upload
    if has_file and not any(kw in user_input for kw in ("生成", "周报", "报告", "创建", "删除", "查看", "列出", "进度", "导出")):
        return {"intent": "upload_file", "params": {}}

    prompt = build_intent_prompt(user_input, has_file)

    try:
        raw = llm_generate(prompt=prompt, system=INTENT_SYSTEM, max_tokens=256, temperature=0.1, enable_thinking=False)
        result = _parse_json(raw)
        logger.info("[Intent] LLM识别 | intent={} params={} raw='{}'", result.get("intent"), result.get("params"), raw[:120])
        return result
    except Exception as e:
        logger.warning("[Intent] LLM识别失败, 使用关键词回退 | error={}", e)
        result = _keyword_fallback(user_input, has_file)
        logger.info("[Intent] 关键词回退 | intent={} params={}", result.get("intent"), result.get("params"))
        return result


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


def _keyword_fallback(user_input: str, has_file: bool) -> dict:
    """Simple keyword-based fallback when LLM fails."""
    text = user_input.lower()

    if has_file:
        return {"intent": "upload_file", "params": {}}

    if any(kw in text for kw in ("创建项目", "新建项目", "添加项目")):
        return {"intent": "create_project", "params": {}}

    if any(kw in text for kw in ("项目列表", "有哪些项目", "列出项目", "查看项目", "我的项目")):
        return {"intent": "list_projects", "params": {}}

    if any(kw in text for kw in ("删除项目", "移除项目")):
        return {"intent": "delete_project", "params": {}}

    if any(kw in text for kw in ("修改项目", "更新项目", "变更项目")):
        return {"intent": "update_project", "params": {}}

    if any(kw in text for kw in ("记录进度", "汇报进度", "更新进度", "进度记录")):
        return {"intent": "record_progress", "params": {}}

    if any(kw in text for kw in ("进度列表", "查看进度", "进度情况")):
        return {"intent": "list_progress", "params": {}}

    if any(kw in text for kw in ("生成周报", "写周报", "撰写周报", "生成报告", "写报告")):
        return {"intent": "generate_report", "params": {}}

    if any(kw in text for kw in ("周报列表", "查看周报", "有哪些周报")):
        return {"intent": "list_reports", "params": {}}

    if any(kw in text for kw in ("导出周报", "下载周报", "导出报告")):
        return {"intent": "export_report", "params": {}}

    # Default to query
    return {"intent": "query", "params": {"question": user_input}}
