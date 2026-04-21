"""Model routing and fallback chain."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from loguru import logger

from agent.llm.base import BaseLLM, LLMRequest, LLMResponse
from agent.llm.local_provider import LocalProvider, llm_generate


class ModelTier(str, Enum):
    FAST = "fast"
    STANDARD = "standard"
    POWERFUL = "powerful"


@dataclass(slots=True)
class ModelConfig:
    tier: ModelTier
    backend: str
    model_name: str
    max_tokens: int = 2048
    temperature: float = 0.7
    timeout: float = 120.0


@dataclass(slots=True)
class RouteDecision:
    task: str
    provider_names: list[str]


_DEFAULT_TASK_ROUTING: dict[str, ModelTier] = {
    "intent_recognition": ModelTier.FAST,
    "keyword_extraction": ModelTier.FAST,
    "classification": ModelTier.FAST,
    "summary_extraction": ModelTier.FAST,
    "planning": ModelTier.STANDARD,
    "progress_query": ModelTier.STANDARD,
    "data_analysis": ModelTier.STANDARD,
    "report_generation": ModelTier.POWERFUL,
    "report_review": ModelTier.POWERFUL,
    "multi_step_reasoning": ModelTier.POWERFUL,
}


class ModelRouter:
    """Rule-based task-to-model routing."""

    def __init__(self) -> None:
        self._task_routing = dict(_DEFAULT_TASK_ROUTING)
        self._tier_configs: dict[ModelTier, ModelConfig] = {}

    def register_task_route(self, task: str, tier: ModelTier) -> None:
        self._task_routing[task] = tier

    def select(self, task: str, **hints) -> ModelConfig:
        del hints
        tier = self._task_routing.get(task, ModelTier.STANDARD)
        if tier in self._tier_configs:
            return self._tier_configs[tier]
        return ModelConfig(tier=tier, backend="", model_name="")

    def generate(self, task: str, prompt: str, system: str = "", **kwargs) -> str:
        config = self.select(task)
        logger.info("[ModelRouter] task='{}' tier={}", task, config.tier.value)
        return llm_generate(
            prompt=prompt,
            system=system,
            max_tokens=kwargs.get("max_tokens", config.max_tokens),
            temperature=kwargs.get("temperature", config.temperature),
            enable_thinking=kwargs.get("enable_thinking", True),
        )


class LLMRouter:
    """Provider router with fallback chain."""

    def __init__(self) -> None:
        self._providers: dict[str, BaseLLM] = {"local": LocalProvider()}
        self._routing = {
            "intent_recognition": ["local"],
            "planning": ["local"],
            "reasoning": ["openai", "anthropic", "local"],
            "review": ["anthropic", "openai", "local"],
            "default": ["local"],
        }

    def register(self, name: str, provider: BaseLLM) -> None:
        self._providers[name] = provider

    def decide(self, task: str) -> RouteDecision:
        return RouteDecision(task=task, provider_names=self._routing.get(task, self._routing["default"]))

    async def generate(self, task: str, request: LLMRequest) -> LLMResponse:
        decision = self.decide(task)
        last_error: Exception | None = None

        for name in decision.provider_names:
            provider = self._providers.get(name)
            if provider is None:
                continue
            try:
                return await provider.generate(request)
            except Exception as exc:
                last_error = exc
                continue

        raise RuntimeError(f"No provider succeeded for task '{task}': {last_error}")


model_router = ModelRouter()
