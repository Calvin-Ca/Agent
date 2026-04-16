"""Model service layer — embedding, LLM, VLM providers.

Supports 2 backends:
  - api:    vLLM / TGI OpenAI-compatible endpoint (生产推荐)
  - ollama: Ollama HTTP API
"""

from app.model_service.embedding import embed_texts
from app.model_service.llm import llm_generate
from app.model_service.vlm import vlm_describe
from app.model_service.registry import model_registry, auto_discover_models

__all__ = [
    "embed_texts",
    "llm_generate",
    "vlm_describe",
    "model_registry",
    "auto_discover_models",
]
