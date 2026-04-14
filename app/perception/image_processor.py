"""Image processor — OCR text extraction + optional VLM description.

Strategy:
1. Try PaddleOCR (best for Chinese text in site photos)
2. Fallback to Tesseract if PaddleOCR not available
3. Optionally call VLM (via Ollama) for scene description
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PIL import Image

from app.config import get_settings
from app.perception.base import ExtractionResult


class ImageProcessor:
    """Image document processor with OCR + VLM support."""

    def supports(self, file_type: str) -> bool:
        return file_type in ("image", "png", "jpg", "jpeg", "bmp", "tiff")

    def extract(self, file_path: str) -> ExtractionResult:
        """Extract text and description from an image."""
        return extract_from_image(file_path)


def extract_from_image(file_path: str | Path, use_vlm: bool = True) -> ExtractionResult:
    """Extract text and description from an image.

    Returns:
        ExtractionResult with ocr_text, vlm_description, and metadata
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Image not found: {file_path}")

    # Get image dimensions
    with Image.open(file_path) as img:
        width, height = img.size

    result = ExtractionResult(metadata={"width": width, "height": height})

    # ── OCR ───────────────────────────────────────────────────
    result.ocr_text = _ocr_extract(file_path)

    # ── VLM description ──────────────────────────────────────
    if use_vlm:
        result.vlm_description = _vlm_describe(file_path)

    return result


def _ocr_extract(file_path: Path) -> str:
    """Try PaddleOCR first, fallback to Tesseract."""
    # Try PaddleOCR
    try:
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        ocr_result = ocr.ocr(str(file_path), cls=True)

        lines = []
        if ocr_result and ocr_result[0]:
            for line in ocr_result[0]:
                text = line[1][0]  # (text, confidence)
                if text.strip():
                    lines.append(text.strip())

        text = "\n".join(lines)
        if text:
            logger.info("PaddleOCR: {} chars from {}", len(text), file_path.name)
            return text

    except ImportError:
        logger.debug("PaddleOCR not installed, trying Tesseract")
    except Exception as e:
        logger.warning("PaddleOCR failed for {}: {}", file_path.name, e)

    # Fallback: Tesseract
    try:
        import pytesseract

        with Image.open(file_path) as img:
            text = pytesseract.image_to_string(img, lang="chi_sim+eng").strip()

        if text:
            logger.info("Tesseract: {} chars from {}", len(text), file_path.name)
            return text

    except ImportError:
        logger.debug("Tesseract not installed")
    except Exception as e:
        logger.warning("Tesseract failed for {}: {}", file_path.name, e)

    logger.warning("No OCR text extracted from {}", file_path.name)
    return ""


def _vlm_describe(file_path: Path) -> str:
    """Call VLM to describe the image content via model_service."""
    try:
        from app.model_service.vlm import vlm_describe
        return vlm_describe(file_path)
    except Exception as e:
        logger.warning("VLM description failed for {}: {}", file_path.name, e)
        return ""
