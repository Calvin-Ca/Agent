"""Model registry — manage multiple models and switch between them.

Supports registering models by alias and switching at runtime without
restarting the server. Useful for A/B testing different models.

Usage:
    from app.model_service.registry import model_registry

    # List available models
    model_registry.list_models("embedding")

    # Switch embedding model at runtime
    model_registry.switch("embedding", "bge-m3")
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path

from loguru import logger


@dataclass
class ModelInfo:
    """Metadata for a registered model."""
    alias: str                          # Short name: "bge-large-zh"
    model_type: str                     # "embedding" | "llm" | "vlm"
    path: str                           # Local path or model name
    backend: str = "local"              # "local" | "api" | "ollama"
    device: str = "cuda"
    description: str = ""
    extra: dict = field(default_factory=dict)


class ModelRegistry:
    """Central registry for all available models."""

    def __init__(self):
        self._models: dict[str, dict[str, ModelInfo]] = {
            "embedding": {},
            "llm": {},
            "vlm": {},
        }
        self._active: dict[str, str] = {}  # model_type -> active alias
        self._lock = threading.Lock()

    def register(self, info: ModelInfo) -> None:
        """Register a model. Overwrites if alias exists."""
        with self._lock:
            self._models[info.model_type][info.alias] = info
            # First registered model of each type becomes active
            if info.model_type not in self._active:
                self._active[info.model_type] = info.alias
            logger.info("Registered {} model: {} ({})", info.model_type, info.alias, info.backend)

    def get_active(self, model_type: str) -> ModelInfo | None:
        """Get the currently active model for a type."""
        alias = self._active.get(model_type)
        if alias is None:
            return None
        return self._models.get(model_type, {}).get(alias)

    def switch(self, model_type: str, alias: str) -> ModelInfo:
        """Switch the active model for a type.

        Unloads the previous model from memory if it was loaded locally.
        """
        with self._lock:
            models = self._models.get(model_type, {})
            if alias not in models:
                available = list(models.keys())
                raise ValueError(f"Model '{alias}' not found. Available: {available}")

            old_alias = self._active.get(model_type)

            # Unload previous model if switching
            if old_alias and old_alias != alias:
                self._unload(model_type)

            self._active[model_type] = alias
            info = models[alias]
            logger.info("Switched {} model: {} → {} ({})", model_type, old_alias, alias, info.backend)
            return info

    def list_models(self, model_type: str | None = None) -> dict:
        """List registered models. Returns {type: [{alias, path, active}, ...]}"""
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

    def _unload(self, model_type: str) -> None:
        """Unload the current model from GPU memory."""
        try:
            if model_type == "embedding":
                from app.model_service.embedding import unload_embedder
                unload_embedder()
            elif model_type == "llm":
                from app.model_service.llm import unload_llm
                unload_llm()
        except Exception as e:
            logger.warning("Failed to unload {} model: {}", model_type, e)


# Singleton
model_registry = ModelRegistry()


def auto_discover_models() -> None:
    """Scan the models/ directory and register all found models.

    Call this at app startup.
    """
    from app.config import get_settings
    settings = get_settings()
    root = Path(settings.model_root)

    if not root.exists():
        logger.warning("Model root not found: {}", root)
        return

    # Scan each category
    type_dirs = {
        "embedding": root / "embeddings",
        "llm": root / "llm",
        "vlm": root / "vlm",
    }

    for model_type, dir_path in type_dirs.items():
        if not dir_path.exists():
            continue

        for model_dir in sorted(dir_path.iterdir()):
            if not model_dir.is_dir():
                continue
            # Skip incomplete downloads (no config files)
            has_config = any(
                (model_dir / f).exists()
                for f in ("config.json", "tokenizer_config.json", "sentence_bert_config.json")
            )
            if not has_config:
                continue

            alias = model_dir.name
            model_registry.register(ModelInfo(
                alias=alias,
                model_type=model_type,
                path=str(model_dir),
                backend="local",
                description=f"Auto-discovered from {model_dir}",
            ))

    # Also register Ollama models if configured
    if settings.ollama_base_url:
        model_registry.register(ModelInfo(
            alias=f"ollama:{settings.ollama_llm_model}",
            model_type="llm",
            path=settings.ollama_llm_model,
            backend="ollama",
            description="Ollama LLM",
        ))
        model_registry.register(ModelInfo(
            alias=f"ollama:{settings.ollama_embed_model}",
            model_type="embedding",
            path=settings.ollama_embed_model,
            backend="ollama",
            description="Ollama Embedding",
        ))

    # Set active models from config
    embed_alias = Path(settings.embed_model_path).name
    llm_alias = Path(settings.llm_model_path).name

    for alias in [embed_alias, f"ollama:{settings.ollama_embed_model}"]:
        if alias in model_registry._models.get("embedding", {}):
            model_registry._active["embedding"] = alias
            break

    for alias in [llm_alias, f"ollama:{settings.ollama_llm_model}"]:
        if alias in model_registry._models.get("llm", {}):
            model_registry._active["llm"] = alias
            break

    logger.info("Model registry: {}", model_registry.list_models())