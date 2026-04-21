"""OpenAI provider adapter."""

from __future__ import annotations

import os

from agent.llm.base import BaseLLM, LLMRequest, LLMResponse


class OpenAIProvider(BaseLLM):
    """Lazy OpenAI adapter to avoid hard dependency at import time."""

    provider_name = "openai"

    def __init__(self, api_key: str | None = None, base_url: str | None = None) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "")

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not configured")

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url or None)
        response = await client.chat.completions.create(
            model=request.model or "gpt-4o-mini",
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            messages=[
                {"role": "system", "content": request.system},
                {"role": "user", "content": request.prompt},
            ],
        )
        text = response.choices[0].message.content or ""
        return LLMResponse(
            text=text,
            model=response.model,
            provider=self.provider_name,
            raw=response.model_dump(),
        )
