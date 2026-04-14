"""Text processor — clean, normalize, and prepare text for chunking."""

from __future__ import annotations

import re
from pathlib import Path

from loguru import logger

from app.perception.base import ExtractionResult


class TextProcessor:
    """Plain text / Markdown / CSV document processor."""

    def supports(self, file_type: str) -> bool:
        return file_type in ("text", "txt", "md", "csv")

    def extract(self, file_path: str) -> ExtractionResult:
        """Read and clean a plain text file."""
        raw = extract_from_text(file_path)
        return ExtractionResult(text=raw["text"], metadata={"line_count": raw["line_count"]})


def extract_from_text(file_path: str | Path) -> dict:
    """Read and clean a plain text file (txt, md, csv).

    Returns:
        {"text": "cleaned text...", "line_count": int}
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"Text file not found: {file_path}")

    # Try UTF-8 first, fallback to GBK (common in Chinese systems)
    for encoding in ("utf-8", "gbk", "gb2312", "latin-1"):
        try:
            raw = file_path.read_text(encoding=encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        raise ValueError(f"Cannot decode {file_path.name} with any supported encoding")

    cleaned = clean_text(raw)
    line_count = len(cleaned.splitlines())
    logger.info("Text: {} lines, {} chars from {}", line_count, len(cleaned), file_path.name)

    return {"text": cleaned, "line_count": line_count}


def clean_text(text: str) -> str:
    """Clean and normalize raw text."""
    if not text:
        return ""

    # Normalize whitespace
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove excessive blank lines (keep max 2)
    text = re.sub(r"\n{3,}", "\n\n", text)

    # Remove leading/trailing whitespace per line
    lines = [line.strip() for line in text.splitlines()]
    text = "\n".join(lines)

    # Remove null bytes and control characters (except newline, tab)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", text)

    return text.strip()


def merge_extracted_content(
    text: str = "",
    tables: list[dict] | None = None,
    ocr_text: str = "",
    vlm_description: str = "",
) -> str:
    """Merge all extracted content into a single document string.

    Used to combine PDF text + tables + image OCR + VLM description
    before chunking.
    """
    parts = []

    if text:
        parts.append(text)

    if tables:
        for t in tables:
            page = t.get("page", "?")
            data = t.get("data", [])
            if not data:
                continue
            # Convert table to markdown-like format
            header = " | ".join(data[0]) if data else ""
            rows = [" | ".join(row) for row in data[1:]]
            table_str = f"[表格 - 第{page}页]\n{header}\n" + "\n".join(rows)
            parts.append(table_str)

    if ocr_text:
        parts.append(f"[图片OCR文字]\n{ocr_text}")

    if vlm_description:
        parts.append(f"[图片描述]\n{vlm_description}")

    return "\n\n".join(parts)
