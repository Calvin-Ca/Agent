"""Base abstractions for model providers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class LLMRequest:
    """Provider-agnostic generation request."""

    prompt: str
    system: str = ""
    model: str = ""
    temperature: float = 0.2
    max_tokens: int = 1024
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class LLMResponse:
    """Provider-agnostic generation response."""

    text: str
    model: str
    provider: str
    raw: Any = None


class BaseLLM(ABC):
    """Unified async interface for all providers."""

    provider_name: str = "base"

    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """Generate text for the given request."""

