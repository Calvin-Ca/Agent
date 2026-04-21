"""Anthropic provider adapter."""

from __future__ import annotations

import os

from agent.llm.base import BaseLLM, LLMRequest, LLMResponse


class AnthropicProvider(BaseLLM):
    """Lazy Anthropic adapter to avoid hard dependency at import time."""

    provider_name = "anthropic"

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not configured")

        from anthropic import AsyncAnthropic

        client = AsyncAnthropic(api_key=self.api_key)
        response = await client.messages.create(
            model=request.model or "claude-3-5-sonnet-latest",
            max_tokens=request.max_tokens,
            temperature=request.temperature,
            system=request.system,
            messages=[{"role": "user", "content": request.prompt}],
        )
        parts = [block.text for block in response.content if getattr(block, "type", "") == "text"]
        return LLMResponse(
            text="".join(parts),
            model=response.model,
            provider=self.provider_name,
            raw=response.model_dump(),
        )
