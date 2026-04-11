"""Model service layer — embedding, LLM, VLM providers.

Supports 3 backends per model type:
  - local:  sentence-transformers / transformers (GPU, fastest for single-machine)
  - api:    vLLM / TGI OpenAI-compatible endpoint (multi-GPU, production)
  - ollama: Ollama HTTP API (easiest setup, moderate performance)
"""

from app.model_service.embedding import get_embedder, embed_texts
from app.model_service.llm import get_llm, llm_generate
from app.model_service.vlm import vlm_describe
from app.model_service.registry import model_registry, auto_discover_models

__all__ = [
    "get_embedder",
    "embed_texts",
    "get_llm",
    "llm_generate",
    "vlm_describe",
    "model_registry",
    "auto_discover_models",
]