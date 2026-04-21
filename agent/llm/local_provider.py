"""Local provider plus sync helpers for generation, embeddings, and VLM."""

from __future__ import annotations

import asyncio
import base64
import time
from pathlib import Path

from loguru import logger

from agent.infra.config import get_settings
from agent.infra.metrics import record_llm_call
from agent.llm.base import BaseLLM, LLMRequest, LLMResponse

_DEFAULT_BATCH_SIZE = 32


class LocalProvider(BaseLLM):
    """Use the configured local backend as the default provider."""

    provider_name = "local"

    async def generate(self, request: LLMRequest) -> LLMResponse:
        loop = asyncio.get_running_loop()
        text = await loop.run_in_executor(
            None,
            lambda: llm_generate(
                prompt=request.prompt,
                system=request.system,
                max_tokens=request.max_tokens,
                temperature=request.temperature,
                enable_thinking=bool(request.metadata.get("enable_thinking", True)),
            ),
        )
        return LLMResponse(
            text=text,
            model=request.model or get_settings().llm_model_name,
            provider=self.provider_name,
        )


def llm_generate(
    prompt: str,
    system: str = "",
    max_tokens: int | None = None,
    temperature: float = 0.7,
    enable_thinking: bool = True,
) -> str:
    """Generate text from the configured LLM backend."""
    settings = get_settings()
    if settings.backend == "vllm":
        return _generate_via_api(prompt, system, max_tokens, temperature, enable_thinking)
    if settings.backend == "ollama":
        return _generate_via_ollama(prompt, system, max_tokens, temperature, enable_thinking)
    raise ValueError(f"不支持的 LLM 后端: {settings.backend}，可选: vllm / ollama")


def embed_texts(
    texts: list[str],
    batch_size: int | None = None,
    normalize: bool = True,
) -> list[list[float]]:
    """Generate embeddings for a list of texts."""
    del normalize
    if not texts:
        return []

    settings = get_settings()
    if settings.backend == "vllm":
        return _embed_via_api(texts, batch_size)
    if settings.backend == "ollama":
        return _embed_via_ollama(texts, batch_size)
    raise ValueError(f"不支持的 Embedding 后端: {settings.backend}，可选: vllm / ollama")


def vlm_describe(
    image_path: str | Path,
    prompt: str = "请用中文详细描述这张工程现场图片的内容，包括施工进度、设备、人员、环境等信息。",
) -> str:
    """Describe an image using the configured VLM backend."""
    settings = get_settings()
    if not settings.vlm_enabled:
        logger.debug("VLM disabled, skipping image description")
        return ""

    path = Path(image_path)
    if not path.exists():
        logger.warning("Image not found: {}", path)
        return ""

    if settings.backend == "vllm":
        return _describe_via_api(path, prompt)
    if settings.backend == "ollama":
        return _describe_via_ollama(path, prompt)
    logger.warning("Unsupported VLM backend {}", settings.backend)
    return ""


def _generate_via_api(
    prompt: str,
    system: str,
    max_tokens: int | None,
    temperature: float,
    enable_thinking: bool,
) -> str:
    import httpx

    settings = get_settings()
    max_tokens_resolved = max_tokens or settings.llm_max_tokens
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    payload: dict = {
        "model": settings.llm_model_name,
        "messages": messages,
        "max_tokens": max_tokens_resolved,
        "temperature": temperature,
    }
    if not enable_thinking:
        payload["chat_template_kwargs"] = {"enable_thinking": False}

    started_at = time.perf_counter()
    response = httpx.post(
        f"{settings.llm_api_base}/chat/completions",
        json=payload,
        headers=headers,
        timeout=120,
    )
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    response.raise_for_status()

    data = response.json()
    content = data["choices"][0]["message"]["content"].strip()
    usage = data.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    record_llm_call(
        backend="vllm",
        elapsed_seconds=elapsed_ms / 1000,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )
    return content


def _generate_via_ollama(
    prompt: str,
    system: str,
    max_tokens: int | None,
    temperature: float,
    enable_thinking: bool,
) -> str:
    import httpx

    settings = get_settings()
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload: dict = {
        "model": settings.ollama_llm_model,
        "messages": messages,
        "stream": False,
        "options": {
            "num_predict": max_tokens or settings.llm_max_tokens,
            "temperature": temperature,
        },
    }
    if not enable_thinking:
        payload["think"] = False

    started_at = time.perf_counter()
    response = httpx.post(
        f"{settings.ollama_base_url}/api/chat",
        json=payload,
        timeout=120,
    )
    elapsed_ms = (time.perf_counter() - started_at) * 1000
    response.raise_for_status()

    data = response.json()
    content = data.get("message", {}).get("content", "").strip()
    record_llm_call(
        backend="ollama",
        elapsed_seconds=elapsed_ms / 1000,
        prompt_tokens=data.get("prompt_eval_count", 0),
        completion_tokens=data.get("eval_count", 0),
    )
    return content


def _embed_via_api(texts: list[str], batch_size: int | None = None) -> list[list[float]]:
    import httpx

    settings = get_settings()
    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    resolved_batch_size = batch_size or _DEFAULT_BATCH_SIZE
    all_embeddings: list[list[float]] = []

    for index in range(0, len(texts), resolved_batch_size):
        batch = texts[index : index + resolved_batch_size]
        try:
            response = httpx.post(
                f"{settings.embed_api_base}/embeddings",
                json={"model": settings.embed_model_name, "input": batch},
                headers=headers,
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()
            all_embeddings.extend(item["embedding"] for item in data["data"])
        except Exception as exc:
            logger.error("API embedding failed for batch {}: {}", index, exc)
            all_embeddings.extend([[0.0] * settings.milvus_dim] * len(batch))

    return all_embeddings


def _embed_via_ollama(texts: list[str], batch_size: int | None = None) -> list[list[float]]:
    import httpx

    settings = get_settings()
    resolved_batch_size = batch_size or _DEFAULT_BATCH_SIZE
    all_embeddings: list[list[float]] = []

    for index in range(0, len(texts), resolved_batch_size):
        batch = texts[index : index + resolved_batch_size]
        try:
            response = httpx.post(
                f"{settings.ollama_base_url}/api/embed",
                json={"model": settings.ollama_embed_model, "input": batch},
                timeout=120,
            )
            response.raise_for_status()
            all_embeddings.extend(response.json().get("embeddings", []))
        except Exception as exc:
            logger.error("Ollama embedding failed for batch {}: {}", index, exc)
            all_embeddings.extend([[0.0] * settings.milvus_dim] * len(batch))

    return all_embeddings


def _describe_via_api(image_path: Path, prompt: str) -> str:
    import httpx

    settings = get_settings()
    image_b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    media_type = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }.get(image_path.suffix.lower(), "image/jpeg")

    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    response = httpx.post(
        f"{settings.llm_api_base}/chat/completions",
        json={
            "model": settings.vlm_model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{image_b64}"}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "max_tokens": 512,
        },
        headers=headers,
        timeout=60,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def _describe_via_ollama(image_path: Path, prompt: str) -> str:
    import httpx

    settings = get_settings()
    image_b64 = base64.b64encode(image_path.read_bytes()).decode("utf-8")
    response = httpx.post(
        f"{settings.ollama_base_url}/api/chat",
        json={
            "model": settings.ollama_vlm_model,
            "messages": [{"role": "user", "content": prompt, "images": [image_b64]}],
            "stream": False,
        },
        timeout=60,
    )
    response.raise_for_status()
    return response.json().get("message", {}).get("content", "").strip()
