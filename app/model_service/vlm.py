"""VLM service — image understanding via vLLM or ollama.

Optional module. Only active when VLM_ENABLED=true.
"""

from __future__ import annotations

import base64
from pathlib import Path

from loguru import logger

from app.config import get_settings


def vlm_describe(
    image_path: str | Path,
    prompt: str = "请用中文详细描述这张工程现场图片的内容，包括施工进度、设备、人员、环境等信息。",
) -> str:
    """Describe an image using VLM.

    Falls back to empty string if VLM is disabled or fails.
    """
    settings = get_settings()

    if not settings.vlm_enabled:
        logger.debug("VLM disabled, skipping image description")
        return ""

    image_path = Path(image_path)
    if not image_path.exists():
        logger.warning("Image not found: {}", image_path)
        return ""

    try:
        if settings.backend == "vllm":
            return _describe_via_api(image_path, prompt)
        if settings.backend == "ollama":
            return _describe_via_ollama(image_path, prompt)
        logger.warning("VLM: unsupported backend {}", settings.backend)
        return ""
    except Exception as e:
        logger.warning("VLM description failed for {}: {}", image_path.name, e)
        return ""


def _describe_via_api(image_path: Path, prompt: str) -> str:
    """Describe using OpenAI-compatible vision API."""
    import httpx

    settings = get_settings()

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    suffix = image_path.suffix.lower()
    media_type = {
        ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".png": "image/png", ".webp": "image/webp",
    }.get(suffix, "image/jpeg")

    headers = {"Content-Type": "application/json"}
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"

    resp = httpx.post(
        f"{settings.llm_api_base}/chat/completions",
        json={
            "model": settings.vlm_model_name,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{img_b64}"}},
                        {"type": "text", "text": prompt},
                    ],
                }
            ],
            "max_tokens": 512,
        },
        headers=headers,
        timeout=60,
    )
    resp.raise_for_status()

    description = resp.json()["choices"][0]["message"]["content"].strip()
    logger.info("VLM API: {} chars for {}", len(description), image_path.name)
    return description


def _describe_via_ollama(image_path: Path, prompt: str) -> str:
    """Describe using Ollama multimodal API."""
    import httpx

    settings = get_settings()

    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode("utf-8")

    resp = httpx.post(
        f"{settings.ollama_base_url}/api/chat",
        json={
            "model": settings.ollama_vlm_model,
            "messages": [
                {
                    "role": "user",
                    "content": prompt,
                    "images": [img_b64],
                }
            ],
            "stream": False,
        },
        timeout=60,
    )
    resp.raise_for_status()

    description = resp.json().get("message", {}).get("content", "").strip()
    logger.info("VLM Ollama: {} chars for {}", len(description), image_path.name)
    return description


if __name__ == "__main__":
    import sys

    settings = get_settings()
    print(f"VLM enabled: {settings.vlm_enabled}")
    print(f"VLM backend: {settings.backend}")

    if not settings.vlm_enabled:
        print("VLM is disabled. Set VLM_ENABLED=true in .env to test.")
        sys.exit(0)

    if len(sys.argv) < 2:
        print("Usage: python -m app.model_service.vlm <image_path>")
        sys.exit(1)

    img = sys.argv[1]
    print(f"Testing vlm_describe({img})...")
    try:
        result = vlm_describe(img)
        print(f"OK: {result[:200]}..." if len(result) > 200 else f"OK: {result}")
    except Exception as e:
        print(f"FAILED: {e}")
