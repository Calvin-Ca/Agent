"""Model router — intelligent model selection based on task characteristics.

Routes LLM requests to the most cost-effective model that meets quality
requirements. Enables using cheaper/faster models for simple tasks
(intent recognition, classification) and powerful models for complex tasks
(report generation, review).

Routing strategies:
1. Rule-based: Map task_type + node → model tier
2. Complexity-based: Estimate prompt complexity → select model (TODO)
3. Cascade: Try fast model first, fall back to powerful model on low confidence (TODO)

Usage:
    from app.model_service.router import model_router

    model_config = model_router.select(
        task="intent_recognition",
        prompt_tokens=200,
    )
    # model_config = ModelConfig(backend="ollama", model="qwen2.5:7b", ...)

    # Or let the router handle the full call:
    result = model_router.generate(
        task="report_generation",
        prompt="...",
        system="...",
    )
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from loguru import logger


class ModelTier(str, Enum):
    """Model tiers ordered by capability / cost."""

    FAST = "fast"           # Small models for simple tasks (7B, classification)
    STANDARD = "standard"   # Medium models for most tasks (14B-32B)
    POWERFUL = "powerful"    # Large models for complex generation (70B+, API)


@dataclass
class ModelConfig:
    """Resolved model configuration for a specific request.

    Attributes:
        tier: The selected model tier.
        backend: LLM backend to use (vllm / ollama).
        model_name: Specific model identifier.
        max_tokens: Token limit for this request.
        temperature: Sampling temperature.
        timeout: Request timeout in seconds.
    """

    tier: ModelTier
    backend: str
    model_name: str
    max_tokens: int = 2048
    temperature: float = 0.7
    timeout: float = 120.0


# ── Default routing rules ─────────────────────────────────────────────────

# Maps (task_name) → ModelTier
_DEFAULT_TASK_ROUTING: dict[str, ModelTier] = {
    # Simple tasks → fast model
    "intent_recognition": ModelTier.FAST,
    "keyword_extraction": ModelTier.FAST,
    "classification": ModelTier.FAST,
    "summary_extraction": ModelTier.FAST,

    # Standard tasks → standard model
    "planning": ModelTier.STANDARD,
    "progress_query": ModelTier.STANDARD,
    "data_analysis": ModelTier.STANDARD,

    # Complex tasks → powerful model
    "report_generation": ModelTier.POWERFUL,
    "report_review": ModelTier.POWERFUL,
    "multi_step_reasoning": ModelTier.POWERFUL,
}


class ModelRouter:
    """Routes LLM requests to appropriate models based on task type and complexity.

    The router maintains a mapping of model tiers → model configurations,
    loaded from app settings. Task routing rules determine which tier to use.

    TODO: Implement actual model config loading from settings.
    """

    def __init__(self):
        self._task_routing: dict[str, ModelTier] = dict(_DEFAULT_TASK_ROUTING)
        self._tier_configs: dict[ModelTier, ModelConfig] = {}
        self._initialized = False

    def initialize(self) -> None:
        """Load model configurations from app settings.

        Should be called once at app startup after settings are loaded.

        TODO: Read from app.config.get_settings() to populate tier configs.
        """
        if self._initialized:
            return

        # TODO: Load from settings
        # settings = get_settings()
        # self._tier_configs = {
        #     ModelTier.FAST: ModelConfig(
        #         tier=ModelTier.FAST,
        #         backend="ollama",
        #         model_name="qwen2.5:7b",
        #         max_tokens=512,
        #         temperature=0.1,
        #         timeout=30.0,
        #     ),
        #     ModelTier.STANDARD: ModelConfig(
        #         tier=ModelTier.STANDARD,
        #         backend=settings.backend,
        #         model_name=settings.llm_model_name,
        #         max_tokens=1024,
        #         temperature=0.3,
        #         timeout=60.0,
        #     ),
        #     ModelTier.POWERFUL: ModelConfig(
        #         tier=ModelTier.POWERFUL,
        #         backend=settings.backend,
        #         model_name=settings.llm_model_name,
        #         max_tokens=2048,
        #         temperature=0.3,
        #         timeout=120.0,
        #     ),
        # }

        self._initialized = True
        logger.info("[ModelRouter] initialized with {} tier configs", len(self._tier_configs))

    def register_task_route(self, task: str, tier: ModelTier) -> None:
        """Register or override a task → tier mapping."""
        self._task_routing[task] = tier

    def select(self, task: str, **hints) -> ModelConfig:
        """Select the best model config for a given task.

        Args:
            task: Task name (e.g., "report_generation", "intent_recognition").
            **hints: Optional hints (prompt_tokens, complexity_score, etc.).

        Returns:
            ModelConfig for the selected model.

        TODO: Implement complexity-based and cascade routing strategies.
        """
        tier = self._task_routing.get(task, ModelTier.STANDARD)

        # If tier config is registered, use it
        if tier in self._tier_configs:
            config = self._tier_configs[tier]
            logger.debug("[ModelRouter] task='{}' → tier={} model={}", task, tier.value, config.model_name)
            return config

        # Fallback: return a default config using current settings
        logger.debug("[ModelRouter] task='{}' → tier={} (fallback to default)", task, tier.value)
        return ModelConfig(
            tier=tier,
            backend="",  # Will use default from settings
            model_name="",  # Will use default from settings
        )

    def generate(self, task: str, prompt: str, system: str = "", **kwargs) -> str:
        """Select model and generate text in one call.

        This is a convenience method that combines select() + llm_generate().

        Args:
            task: Task name for model routing.
            prompt: The user prompt.
            system: Optional system prompt.
            **kwargs: Passed to llm_generate().

        Returns:
            Generated text.

        TODO: Implement with actual model dispatch.
        """
        config = self.select(task)
        logger.info("[ModelRouter] generate task='{}' tier={}", task, config.tier.value)

        # TODO: Dispatch to the selected backend/model
        # For now, fall back to the default llm_generate
        from app.model_service.llm import llm_generate

        return llm_generate(
            prompt=prompt,
            system=system,
            max_tokens=kwargs.get("max_tokens", config.max_tokens),
            temperature=kwargs.get("temperature", config.temperature),
        )


# Singleton
model_router = ModelRouter()
