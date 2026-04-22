"""Prompt helpers for planning and intent recognition — loaded from .j2 templates."""

from __future__ import annotations

from agent.prompts.loader import load, render

PLANNER_PROMPT = load("planner.j2")
INTENT_PROMPT = None  # Template-based; use build_intent_prompt() instead.


def build_intent_prompt(user_input: str, has_file: bool) -> str:
    """Build the prompt used for intent recognition."""
    return render(
        "intent.j2",
        user_input=user_input,
        has_file="是" if has_file else "否",
    )
