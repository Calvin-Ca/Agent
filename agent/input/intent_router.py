"""Intent routing and classification."""

from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from loguru import logger

from agent.input.preprocessor import UnifiedMessage
from agent.infra.logger import run_in_executor_with_context
from agent.llm.local_provider import llm_generate
from agent.prompts.planner import build_intent_prompt
from agent.prompts.system import INTENT_SYSTEM


@dataclass(slots=True)
class RoutedIntent:
    """Intent classification output."""

    intent: str
    params: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0


class IntentRouter:
    """Resolve an incoming message to a downstream capability."""

    def __init__(
        self,
        recognizer: Callable[[str, bool], dict[str, Any]] | None = None,
    ) -> None:
        self._recognizer = recognizer or recognize_intent

    async def route(self, message: UnifiedMessage) -> RoutedIntent:
        loop = asyncio.get_running_loop()
        result = await run_in_executor_with_context(
            loop,
            self._recognizer,
            message.content,
            bool(message.attachments),
        )
        return RoutedIntent(
            intent=result.get("intent", "query"),
            params=result.get("params", {}),
            confidence=float(result.get("confidence", 1.0)),
        )


def recognize_intent(user_input: str, has_file: bool = False) -> dict[str, Any]:
    """Recognize user intent via LLM with keyword fallback."""
    if has_file and not any(
        keyword in user_input for keyword in ("生成", "周报", "报告", "创建", "删除", "查看", "列出", "进度", "导出")
    ):
        return {"intent": "upload_file", "params": {}}

    prompt = build_intent_prompt(user_input, has_file)

    try:
        raw = llm_generate(
            prompt=prompt,
            system=INTENT_SYSTEM,
            max_tokens=256,
            temperature=0.1,
            enable_thinking=False,
        )
        result = _parse_json(raw)
        logger.info("[Intent] LLM resolved intent={} params={}", result.get("intent"), result.get("params"))
        return result
    except Exception as exc:
        logger.warning("[Intent] LLM failed, using keyword fallback: {}", exc)
        return _keyword_fallback(user_input, has_file)


def _parse_json(raw: str) -> dict[str, Any]:
    cleaned = re.sub(r"```(?:json)?\s*", "", raw).strip().rstrip("`")

    try:
        result = json.loads(cleaned)
        if "intent" in result:
            result.setdefault("params", {})
            return result
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\"intent\".*\}", cleaned, re.DOTALL)
    if match:
        result = json.loads(match.group())
        result.setdefault("params", {})
        return result

    raise ValueError(f"Unable to parse intent payload: {raw[:200]}")


def _keyword_fallback(user_input: str, has_file: bool) -> dict[str, Any]:
    text = user_input.lower()

    if has_file:
        return {"intent": "upload_file", "params": {}}
    if any(keyword in text for keyword in ("创建项目", "新建项目", "添加项目")):
        return {"intent": "create_project", "params": {}}
    if any(keyword in text for keyword in ("项目列表", "有哪些项目", "列出项目", "查看项目", "我的项目")):
        return {"intent": "list_projects", "params": {}}
    if any(keyword in text for keyword in ("删除项目", "移除项目")):
        return {"intent": "delete_project", "params": {}}
    if any(keyword in text for keyword in ("修改项目", "更新项目", "变更项目")):
        return {"intent": "update_project", "params": {}}
    if any(keyword in text for keyword in ("记录进度", "汇报进度", "更新进度", "进度记录")):
        return {"intent": "record_progress", "params": {}}
    if any(keyword in text for keyword in ("进度列表", "查看进度", "进度情况")):
        return {"intent": "list_progress", "params": {}}
    if any(keyword in text for keyword in ("生成周报", "写周报", "撰写周报", "生成报告", "写报告")):
        return {"intent": "generate_report", "params": {}}
    if any(keyword in text for keyword in ("周报列表", "查看周报", "有哪些周报")):
        return {"intent": "list_reports", "params": {}}
    if any(keyword in text for keyword in ("导出周报", "下载周报", "导出报告")):
        return {"intent": "export_report", "params": {}}
    return {"intent": "query", "params": {"question": user_input}}
