"""VLM service — image understanding for site photos.

Optional module. Only loaded when VLM_ENABLED=true.
Supports Gemma 4 (natively multimodal), Qwen2-VL, InternVL, etc.

Requires: pip install transformers>=4.51.0
"""

from __future__ import annotations

import base64
import threading
from pathlib import Path

from loguru import logger

from app.config import get_settings

_vlm_model = None
_vlm_processor = None
_lock = threading.Lock()


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
        if settings.llm_backend == "api":
            return _describe_via_api(image_path, prompt)
        elif settings.llm_backend == "ollama":
            return _describe_via_ollama(image_path, prompt)
        else:
            return _describe_local(image_path, prompt)
    except Exception as e:
        logger.warning("VLM description failed for {}: {}", image_path.name, e)
        return ""


def _describe_local(image_path: Path, prompt: str) -> str:
    """Describe using locally loaded VLM (Gemma 4 / Qwen2-VL / etc)."""
    model, processor = _get_vlm()

    from PIL import Image
    import torch

    image = Image.open(image_path).convert("RGB")

    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt},
            ],
        }
    ]

    input_text = processor.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True,
    )

    inputs = processor(
        text=input_text,
        images=[image],
        return_tensors="pt",
    ).to(model.device)

    with torch.no_grad():
        output_ids = model.generate(**inputs, max_new_tokens=512)

    input_len = inputs["input_ids"].shape[1]
    new_tokens = output_ids[0][input_len:]
    description = processor.decode(new_tokens, skip_special_tokens=True).strip()

    logger.info("VLM local: {} chars for {}", len(description), image_path.name)
    return description


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
            "model": Path(settings.vlm_model_path).name,
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
            "model": settings.ollama_llm_model,
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


def _get_vlm():
    """Load VLM model (singleton). Auto-detects the correct model class."""
    global _vlm_model, _vlm_processor
    if _vlm_model is not None:
        return _vlm_model, _vlm_processor

    with _lock:
        if _vlm_model is not None:
            return _vlm_model, _vlm_processor

        settings = get_settings()
        model_path = settings.vlm_model_path

        if not Path(model_path).exists():
            raise FileNotFoundError(f"VLM model not found at: {model_path}")

        logger.info("Loading VLM from {} ...", model_path)

        import json
        import torch
        from transformers import AutoProcessor

        _vlm_processor = AutoProcessor.from_pretrained(model_path, trust_remote_code=True)

        # Auto-detect model class from config.json
        config_path = Path(model_path) / "config.json"
        model_type = ""
        if config_path.exists():
            with open(config_path) as f:
                config = json.load(f)
            model_type = config.get("model_type", "").lower()
            logger.info("Detected model_type: {}", model_type)

        # Pick the right Auto class based on model architecture
        # Gemma 4/3 and most modern VLMs use AutoModelForImageTextToText
        # Older models (Qwen-VL v1, etc) may need AutoModelForVision2Seq
        auto_cls = None
        try:
            from transformers import AutoModelForImageTextToText
            auto_cls = AutoModelForImageTextToText
        except ImportError:
            from transformers import AutoModelForVision2Seq
            auto_cls = AutoModelForVision2Seq
            logger.warning(
                "AutoModelForImageTextToText not available, using AutoModelForVision2Seq. "
                "Consider upgrading: pip install transformers>=4.51.0"
            )

        logger.info("Using model class: {}", auto_cls.__name__)

        _vlm_model = auto_cls.from_pretrained(
            model_path,
            device_map="auto",
            torch_dtype=torch.bfloat16,
            trust_remote_code=True,
        )
        _vlm_model.eval()

        logger.info("VLM loaded: {}", model_path)
        return _vlm_model, _vlm_processor