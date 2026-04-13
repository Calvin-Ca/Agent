"""LLM service — load and call language models.

Supports two backends:
1. "local" — load via transformers AutoModelForCausalLM (for dev/small models)
2. "api"   — call vLLM/TGI OpenAI-compatible endpoint (for production/large models)

Production recommendation:
- Models ≤ 14B: "local" backend works fine on single GPU
- Models > 14B or multi-GPU: deploy with vLLM, use "api" backend
  vllm serve /data/models/llm/qwen2.5-72b --port 8001
"""

from __future__ import annotations

import threading
from pathlib import Path

from loguru import logger

from app.config import get_settings

_llm_model = None
_llm_tokenizer = None
_lock = threading.Lock()


def get_llm():
    """Get or initialize the local LLM model + tokenizer (singleton).

    Returns (model, tokenizer) tuple.
    Only used when llm_backend == "local".
    """
    global _llm_model, _llm_tokenizer
    if _llm_model is not None:
        return _llm_model, _llm_tokenizer

    with _lock:
        if _llm_model is not None:
            return _llm_model, _llm_tokenizer

        settings = get_settings()

        if settings.llm_backend != "local":
            raise RuntimeError(
                f"get_llm() called but LLM_BACKEND={settings.llm_backend}. "
                f"Use llm_generate() which handles both backends."
            )

        model_path = settings.llm_model_path
        if not Path(model_path).exists():
            raise FileNotFoundError(f"LLM model not found at: {model_path}")

        logger.info("Loading LLM from {} ...", model_path)

        from transformers import AutoModelForCausalLM, AutoTokenizer
        import torch

        _llm_tokenizer = AutoTokenizer.from_pretrained(
            model_path, trust_remote_code=True,
        )
        _llm_model = AutoModelForCausalLM.from_pretrained(
            model_path,
            device_map="auto",
            torch_dtype=torch.bfloat16,
            trust_remote_code=True,
        )
        _llm_model.eval()

        logger.info("LLM loaded: {}", model_path)
        return _llm_model, _llm_tokenizer


def llm_generate(
    prompt: str,
    system: str = "",
    max_tokens: int | None = None,
    temperature: float = 0.7,
    stream: bool = False,
) -> str:
    """Generate text from the LLM.

    Dispatches to local / api / ollama backend based on LLM_BACKEND config.
    """
    settings = get_settings()

    if settings.llm_backend == "api":
        return _generate_via_api(prompt, system, max_tokens, temperature)
    elif settings.llm_backend == "ollama":
        return _generate_via_ollama(prompt, system, max_tokens, temperature)
    else:
        return _generate_local(prompt, system, max_tokens, temperature)


def _generate_local(
    prompt: str,
    system: str,
    max_tokens: int | None,
    temperature: float,
) -> str:
    """Generate using locally loaded transformers model."""
    settings = get_settings()
    model, tokenizer = get_llm()
    max_t = max_tokens or settings.llm_max_tokens

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    # Use chat template if available
    if hasattr(tokenizer, "apply_chat_template"):
        input_text = tokenizer.apply_chat_template(
            messages, tokenize=False, add_generation_prompt=True,
        )
    else:
        input_text = f"{system}\n\n{prompt}" if system else prompt

    import torch

    inputs = tokenizer(input_text, return_tensors="pt").to(model.device)

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_t,
            temperature=temperature,
            do_sample=temperature > 0,
            top_p=0.9,
            repetition_penalty=1.05,
        )

    # Decode only the new tokens
    new_tokens = outputs[0][inputs["input_ids"].shape[1] :]
    response = tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

    logger.debug("LLM local: {} input chars → {} output chars", len(input_text), len(response))
    return response


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

    model_name = settings.llm_model_name or Path(settings.llm_model_path).name
    resp = httpx.post(
        f"{settings.llm_api_base}/chat/completions",
        json={
            "model": model_name,
            "messages": messages,
            "max_tokens": max_t,
            "temperature": temperature,
        },
        headers=headers,
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()

    response = data["choices"][0]["message"]["content"].strip()
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


def unload_llm() -> None:
    """Unload LLM from memory."""
    global _llm_model, _llm_tokenizer
    with _lock:
        if _llm_model is not None:
            del _llm_model, _llm_tokenizer
            _llm_model = None
            _llm_tokenizer = None
            logger.info("LLM unloaded")

            try:
                import torch
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except ImportError:
                pass