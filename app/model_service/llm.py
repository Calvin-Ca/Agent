"""LLM service — call language models via vLLM or ollama."""

from __future__ import annotations

import time

from loguru import logger

from app.config import get_settings
from app.agents.callbacks.metrics import record_llm_call


def llm_generate(
    prompt: str,
    system: str = "",
    max_tokens: int | None = None,
    temperature: float = 0.7,
    enable_thinking: bool = True,
) -> str:
    """Generate text from the LLM.

    Dispatches to api / ollama backend based on LLM_BACKEND config.

    Args:
        enable_thinking: 是否返回思考过程（<think>块）。对 DeepSeek-R1 等推理模型，
            设为 False 可让返回结果只包含最终内容，便于结构化解析。
    """
    settings = get_settings()

    if settings.backend == "vllm":
        return _generate_via_api(prompt, system, max_tokens, temperature, enable_thinking)
    if settings.backend == "ollama":
        return _generate_via_ollama(prompt, system, max_tokens, temperature, enable_thinking)

    raise ValueError(f"不支持的 LLM 后端: {settings.backend}，可选: vllm / ollama")


def _generate_via_api(
    prompt: str,
    system: str,
    max_tokens: int | None,
    temperature: float,
    enable_thinking: bool,
) -> str:
    """Generate using OpenAI-compatible API (vLLM/TGI)."""
    import httpx

    settings = get_settings()
    max_t = settings.llm_max_tokens or max_tokens
    model_name = settings.llm_model_name

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    body: dict = {
        "model": model_name,
        "messages": messages,
        "max_tokens": max_t,
        "temperature": temperature,
    }
    if not enable_thinking:
        body["chat_template_kwargs"] = {"enable_thinking": False}

    prompt_preview = prompt[:80].replace("\n", " ")
    logger.info(
        "[LLM] call | backend=vllm model={} max_tokens={} temp={} prompt='{}'",
        model_name, max_t, temperature, prompt_preview,
    )

    start = time.perf_counter()
    resp = httpx.post(
        f"{settings.llm_api_base}/chat/completions",
        json=body,
        headers=headers,
        timeout=120,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    resp.raise_for_status()

    data = resp.json()
    response = data["choices"][0]["message"]["content"].strip()

    # Extract token usage if available
    usage = data.get("usage", {})
    prompt_tokens = usage.get("prompt_tokens", 0)
    completion_tokens = usage.get("completion_tokens", 0)
    total_tokens = usage.get("total_tokens", "-")

    logger.info(
        "[LLM] done | {:.0f}ms | tokens: in={} out={} total={} | output_chars={}",
        elapsed_ms, prompt_tokens, completion_tokens, total_tokens, len(response),
    )

    record_llm_call(
        backend="vllm",
        elapsed_seconds=elapsed_ms / 1000,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )

    return response


def _generate_via_ollama(
    prompt: str,
    system: str,
    max_tokens: int | None,
    temperature: float,
    enable_thinking: bool,
) -> str:
    """Generate using Ollama HTTP API."""
    import httpx

    settings = get_settings()
    model_name = settings.ollama_llm_model

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    body: dict = {
        "model": model_name,
        "messages": messages,
        "stream": False,
        "options": {
            "num_predict": max_tokens or settings.llm_max_tokens,
            "temperature": temperature,
        },
    }
    if not enable_thinking:
        body["think"] = False

    prompt_preview = prompt[:80].replace("\n", " ")
    logger.info(
        "[LLM] call | backend=ollama model={} max_tokens={} temp={} prompt='{}'",
        model_name, max_tokens or settings.llm_max_tokens, temperature, prompt_preview,
    )

    start = time.perf_counter()
    resp = httpx.post(
        f"{settings.ollama_base_url}/api/chat",
        json=body,
        timeout=120,
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    resp.raise_for_status()

    data = resp.json()
    response = data.get("message", {}).get("content", "").strip()

    # Ollama returns eval_count / prompt_eval_count
    prompt_tokens = data.get("prompt_eval_count", 0)
    completion_tokens = data.get("eval_count", 0)

    logger.info(
        "[LLM] done | {:.0f}ms | tokens: in={} out={} | output_chars={}",
        elapsed_ms, prompt_tokens, completion_tokens, len(response),
    )

    record_llm_call(
        backend="ollama",
        elapsed_seconds=elapsed_ms / 1000,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )

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
