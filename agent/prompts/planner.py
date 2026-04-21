"""Prompt helpers for planning and intent recognition."""

from __future__ import annotations

PLANNER_PROMPT = """\
Break the user request into the smallest reliable execution steps.
Prefer tool use over unsupported claims, and keep the plan executable.
"""

INTENT_PROMPT = """用户输入：{user_input}
是否附带文件：{has_file}

请识别意图并提取参数。注意：请从用户输入中提取项目名称（project_name），而非项目ID。"""


def build_intent_prompt(user_input: str, has_file: bool) -> str:
    """Build the prompt used for intent recognition."""
    return INTENT_PROMPT.format(
        user_input=user_input,
        has_file="是" if has_file else "否",
    )
