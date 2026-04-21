"""Model registry — manage model metadata and active selection at runtime.

This is the authoritative registry for all model backends (embedding, llm, vlm).
It lives in the agent layer so the agent can switch or inspect models independently
of the HTTP/service layer.

Usage:
    from agent.llm.registry import model_registry, auto_discover_models

    model_registry.list_models("embedding")
    model_registry.switch("embedding", "ollama:bge-large")
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field

from loguru import logger


@dataclass
class ModelInfo:
    """Metadata for a registered model."""

    alias: str
    model_type: str  # "embedding" | "llm" | "vlm"
    path: str        # model name (Ollama model name or vLLM model path)
    backend: str = "vllm"  # "vllm" | "ollama"
    description: str = ""
    extra: dict = field(default_factory=dict)


class ModelRegistry:
    """Central registry for all available models."""

    def __init__(self) -> None:
        self._models: dict[str, dict[str, ModelInfo]] = {
            "embedding": {},
            "llm": {},
            "vlm": {},
        }
        self._active: dict[str, str] = {}
        self._lock = threading.Lock()

    def register(self, info: ModelInfo) -> None:
        with self._lock:
            self._models[info.model_type][info.alias] = info
            if info.model_type not in self._active:
                self._active[info.model_type] = info.alias
            logger.info("Registered {} model: {} ({})", info.model_type, info.alias, info.backend)

    def get_active(self, model_type: str) -> ModelInfo | None:
        alias = self._active.get(model_type)
        if alias is None:
            return None
        return self._models.get(model_type, {}).get(alias)

    def switch(self, model_type: str, alias: str) -> ModelInfo:
        with self._lock:
            models = self._models.get(model_type, {})
            if alias not in models:
                available = list(models.keys())
                raise ValueError(f"Model '{alias}' not found. Available: {available}")
            old_alias = self._active.get(model_type)
            self._active[model_type] = alias
            info = models[alias]
            logger.info("Switched {} model: {} -> {} ({})", model_type, old_alias, alias, info.backend)
            return info

    def list_models(self, model_type: str | None = None) -> dict:
        result = {}
        types = [model_type] if model_type else list(self._models.keys())
        for t in types:
            active_alias = self._active.get(t)
            result[t] = [
                {
                    "alias": info.alias,
                    "path": info.path,
                    "backend": info.backend,
                    "description": info.description,
                    "active": info.alias == active_alias,
                }
                for info in self._models.get(t, {}).values()
            ]
        return result


model_registry = ModelRegistry()


def auto_discover_models() -> None:
    """Register models from config. Call at app startup."""
    from agent.infra.config import get_settings

    settings = get_settings()

    if settings.backend == "vllm":
        model_registry.register(ModelInfo(
            alias=f"vllm:{settings.llm_model_name}",
            model_type="llm",
            path=settings.llm_model_name,
            backend="vllm",
            description=f"vLLM @ {settings.llm_api_base}",
        ))
        model_registry.register(ModelInfo(
            alias=f"vllm:{settings.embed_model_name}",
            model_type="embedding",
            path=settings.embed_model_name,
            backend="vllm",
            description=f"vLLM @ {settings.embed_api_base}",
        ))

    if settings.ollama_base_url:
        model_registry.register(ModelInfo(
            alias=f"ollama:{settings.ollama_llm_model}",
            model_type="llm",
            path=settings.ollama_llm_model,
            backend="ollama",
            description=f"Ollama @ {settings.ollama_base_url}",
        ))
        model_registry.register(ModelInfo(
            alias=f"ollama:{settings.ollama_embed_model}",
            model_type="embedding",
            path=settings.ollama_embed_model,
            backend="ollama",
            description=f"Ollama @ {settings.ollama_base_url}",
        ))

    if settings.backend == "vllm":
        model_registry._active["llm"] = f"vllm:{settings.llm_model_name}"
        model_registry._active["embedding"] = f"vllm:{settings.embed_model_name}"
    else:
        model_registry._active["llm"] = f"ollama:{settings.ollama_llm_model}"
        model_registry._active["embedding"] = f"ollama:{settings.ollama_embed_model}"

    logger.info("Model registry initialized: {}", model_registry.list_models())
