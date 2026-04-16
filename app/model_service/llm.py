"""LLM service — call language models via vLLM or ollama."""

from __future__ import annotations

from loguru import logger

from app.config import get_settings


def llm_generate(
    prompt: str,
    system: str = "",
    max_tokens: int | None = None,
    temperature: float = 0.7,
) -> str:
    """Generate text from the LLM.

    Dispatches to api / ollama backend based on LLM_BACKEND config.
    """
    settings = get_settings()

    if settings.backend == "vllm":
        return _generate_via_api(prompt, system, max_tokens, temperature)
    if settings.backend == "ollama":
        return _generate_via_ollama(prompt, system, max_tokens, temperature)

    raise ValueError(f"不支持的 LLM 后端: {settings.backend}，可选: vllm / ollama")


def _generate_via_api(
    prompt: str,
    system: str,
    max_tokens: int | None,
    temperature: float,
) -> str:
    """Generate using OpenAI-compatible API (vLLM/TGI)."""
    import httpx

    settings = get_settings()
    max_t = max_tokens or settings.llm_max_tokens

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    resp = httpx.post(
        f"{settings.llm_api_base}/chat/completions",
        json={
            "model": settings.llm_model_name,
            "messages": messages,
            "max_tokens": max_t,
            "temperature": temperature,
        },
        headers=headers,
        timeout=120,
    )
    resp.raise_for_status()

    response = resp.json()["choices"][0]["message"]["content"].strip()
    logger.debug("LLM API: {} output chars", len(response))
    return response


def _generate_via_ollama(
    prompt: str,
    system: str,
    max_tokens: int | None,
    temperature: float,
) -> str:
    """Generate using Ollama HTTP API."""
    import httpx

    settings = get_settings()

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    resp = httpx.post(
        f"{settings.ollama_base_url}/api/chat",
        json={
            "model": settings.ollama_llm_model,
            "messages": messages,
            "stream": False,
            "options": {
                "num_predict": max_tokens or settings.llm_max_tokens,
                "temperature": temperature,
            },
        },
        timeout=120,
    )
    resp.raise_for_status()

    response = resp.json().get("message", {}).get("content", "").strip()
    logger.debug("LLM Ollama: {} output chars", len(response))
    return response


if __name__ == "__main__":
    settings = get_settings()
    print(f"LLM backend: {settings.backend}")
    if settings.backend == "vllm":
        print(f"  API: {settings.llm_api_base}  model: {settings.llm_model_name}")
    else:
        print(f"  Ollama: {settings.ollama_base_url}  model: {settings.ollama_llm_model}")

    print("Testing LLM generate...")
    try:
        result = llm_generate("你好，请用一句话介绍你自己。")
        print(f"OK: {result}")
    except Exception as e:
        print(f"FAILED: {e}")
