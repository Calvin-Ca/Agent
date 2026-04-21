"""LLM abstraction layer."""

from agent.llm.base import BaseLLM, LLMRequest, LLMResponse
from agent.llm.local_provider import embed_texts, llm_generate, vlm_describe
from agent.llm.router import LLMRouter, ModelConfig, ModelRouter, ModelTier, model_router

__all__ = [
    "BaseLLM",
    "LLMRequest",
    "LLMResponse",
    "LLMRouter",
    "ModelConfig",
    "ModelRouter",
    "ModelTier",
    "embed_texts",
    "llm_generate",
    "model_router",
    "vlm_describe",
]
