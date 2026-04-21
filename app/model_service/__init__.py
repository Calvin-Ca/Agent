"""Model service layer — embedding, LLM, VLM providers, and intelligent routing.

Supports 2 backends:
  - api:    vLLM / TGI OpenAI-compatible endpoint (production)
  - ollama: Ollama HTTP API

Model router:
  - Routes LLM requests to cost-effective models based on task complexity
  - Supports rule-based, complexity-based, and cascade routing strategies
"""

from app.model_service.embedding import embed_texts
from app.model_service.llm import llm_generate
from app.model_service.vlm import vlm_describe
from app.model_service.registry import model_registry, auto_discover_models
from app.model_service.router import model_router, ModelTier, ModelConfig

__all__ = [
    "embed_texts",
    "llm_generate",
    "vlm_describe",
    "model_registry",
    "auto_discover_models",
    "model_router",
    "ModelTier",
    "ModelConfig",
]
