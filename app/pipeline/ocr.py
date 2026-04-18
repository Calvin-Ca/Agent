"""OCR utilities — unified text extraction from raw image bytes or file paths.

Priority (highest to lowest):
1. Remote PaddleOCR server API  (if PADDLEOCR_API_URL is configured)
2. Local PaddleOCR              (best for Chinese text)
3. Tesseract                    (fallback)

Public API
----------
ocr_extract(file_path)  -> str   # main entry used by processors
ocr_via_api(file_path)  -> str   # remote server only
ocr_via_paddle(file_path) -> str # local PaddleOCR only
ocr_via_tesseract(file_path) -> str  # Tesseract only
"""

from __future__ import annotations

import base64
from pathlib import Path

import httpx
from loguru import logger

from app.config import get_settings


# ── Public entry point ────────────────────────────────────────────────────────

def ocr_extract(file_path: str | Path) -> str:
    """Extract text from an image file using the best available OCR backend.

    Tries backends in order: API → local PaddleOCR → Tesseract.
    Returns the first non-empty result.
    """
    file_path = Path(file_path)

    text = ocr_via_api(file_path)
    if text:
        return text

    text = ocr_via_paddle(file_path)
    if text:
        return text

    text = ocr_via_tesseract(file_path)
    if text:
        return text

    logger.warning("No OCR text extracted from {}", file_path.name)
    return ""


# ── Backend implementations ───────────────────────────────────────────────────

def ocr_via_api(file_path: str | Path) -> str:
    """POST image to a remote PaddleOCR server and return extracted text.

    Disabled (returns "") when ``PADDLEOCR_API_URL`` is not set.

    Supported response shapes
    -------------------------
    Shape A — PaddleServing / paddle_serving_server::

        {"results": [[{"transcription": "...", "points": [...]}]]}

    Shape B — custom FastAPI wrapper::

        {"data": [{"text": "...", "confidence": 0.99}]}
    """
    api_url = get_settings().paddleocr_api_url
    if not api_url:
        return ""

    file_path = Path(file_path)
    img_b64 = base64.b64encode(file_path.read_bytes()).decode()

    try:
        resp = httpx.post(api_url, json={"images": [img_b64]}, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        lines: list[str] = []
        if "results" in data:
            for item in (data["results"] or [[]])[0]:
                t = item.get("transcription", "").strip()
                if t:
                    lines.append(t)
        elif "data" in data:
            for item in data["data"] or []:
                t = item.get("text", "").strip()
                if t:
                    lines.append(t)
        else:
            logger.warning("PaddleOCR API: unexpected response schema from {}", api_url)
            return ""

        text = "\n".join(lines)
        if text:
            logger.info("PaddleOCR API: {} chars from {}", len(text), file_path.name)
        return text

    except httpx.HTTPError as e:
        logger.warning("PaddleOCR API request failed for {}: {}", file_path.name, e)
        return ""
    except Exception as e:
        logger.warning("PaddleOCR API error for {}: {}", file_path.name, e)
        return ""


def ocr_via_paddle(file_path: str | Path) -> str:
    """Extract text using locally installed PaddleOCR.

    Returns "" if PaddleOCR is not installed or fails.
    """
    file_path = Path(file_path)
    try:
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        ocr_result = ocr.ocr(str(file_path), cls=True)

        lines: list[str] = []
        if ocr_result and ocr_result[0]:
            for line in ocr_result[0]:
                t = line[1][0].strip()  # (text, confidence)
                if t:
                    lines.append(t)

        text = "\n".join(lines)
        if text:
            logger.info("PaddleOCR (local): {} chars from {}", len(text), file_path.name)
        return text

    except ImportError:
        logger.debug("PaddleOCR not installed")
        return ""
    except Exception as e:
        logger.warning("PaddleOCR (local) failed for {}: {}", file_path.name, e)
        return ""


def ocr_via_tesseract(file_path: str | Path) -> str:
    """Extract text using Tesseract (chi_sim + eng).

    Returns "" if Tesseract is not installed or fails.
    """
    file_path = Path(file_path)
    try:
        import pytesseract
        from PIL import Image

        with Image.open(file_path) as img:
            text = pytesseract.image_to_string(img, lang="chi_sim+eng").strip()

        if text:
            logger.info("Tesseract: {} chars from {}", len(text), file_path.name)
        return text

    except ImportError:
        logger.debug("Tesseract not installed")
        return ""
    except Exception as e:
        logger.warning("Tesseract failed for {}: {}", file_path.name, e)
        return ""
