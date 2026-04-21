"""Final response safety filters."""

from __future__ import annotations

from typing import Any

from agent.input.guardrails import Guardrails


class OutputGuard:
    """Redact sensitive strings before sending the final response."""

    def __init__(self) -> None:
        self._guardrails = Guardrails()

    def validate(self, result: Any) -> Any:
        return self._redact(result)

    def _redact(self, value: Any) -> Any:
        if isinstance(value, str):
            return self._guardrails.redact(value)
        if isinstance(value, list):
            return [self._redact(item) for item in value]
        if isinstance(value, dict):
            return {key: self._redact(item) for key, item in value.items()}
        return value

