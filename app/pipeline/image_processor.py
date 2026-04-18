"""Image processor — OCR text extraction + optional VLM description.

Strategy:
1. OCR via app.perception.ocr (API → local PaddleOCR → Tesseract)
2. Optionally call VLM (via model_service) for scene description
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger
from PIL import Image

from app.pipeline.base import ExtractionResult
from app.pipeline.ocr import ocr_extract


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

    with Image.open(file_path) as img:
        width, height = img.size

    result = ExtractionResult(metadata={"width": width, "height": height})

    # ── OCR ───────────────────────────────────────────────────
    result.ocr_text = ocr_extract(file_path)

    # ── VLM description ──────────────────────────────────────
    if use_vlm:
        result.vlm_description = _vlm_describe(file_path)

    return result


def _vlm_describe(file_path: Path) -> str:
    """Call VLM to describe the image content via model_service."""
    try:
        from app.model_service.vlm import vlm_describe
        return vlm_describe(file_path)
    except Exception as e:
        logger.warning("VLM description failed for {}: {}", file_path.name, e)
        return ""


if __name__ == "__main__":
    file_path = r"storage\uploads\2d_component\出入口控制系统00.png"
    if not file_path:
        raise SystemExit("Please set 'file_path' in image_processor.py before running.")

    result = extract_from_image(file_path)
    print(result)
