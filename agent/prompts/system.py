"""System prompt constants — loaded from .j2 templates.

Consumers import these constants as before:
    from agent.prompts.system import INTENT_SYSTEM, REPORT_SYSTEM, QUERY_SYSTEM
"""

from __future__ import annotations

from agent.prompts.loader import load

SYSTEM_PROMPT = load("system.j2")
INTENT_SYSTEM = load("intent_system.j2")
REPORT_SYSTEM = load("report_system.j2")
QUERY_SYSTEM = load("query_system.j2")
