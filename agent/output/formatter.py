"""Response synthesis helpers."""

from __future__ import annotations

from typing import Any

from app.core.response import R
from agent.core.state import AgentState


class ResponseFormatter:
    """Apply light post-processing to service responses."""

    def format(self, result: Any, state: AgentState) -> Any:
        if isinstance(result, R):
            if isinstance(result.data, dict):
                result.data.setdefault("intent", state.intent)
            return result
        return result
