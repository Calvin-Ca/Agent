"""Input preprocessing and document extraction helpers."""

from __future__ import annotations

import base64
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx
from fastapi import UploadFile
from loguru import logger

from agent.infra.config import get_settings


@dataclass(slots=True)
class Attachment:
    """Normalized attachment metadata."""

    filename: str
    media_type: str
    kind: str


@dataclass(slots=True)
class UnifiedMessage:
    """Normalized user input consumed by the agent loop."""

    content: str
    attachments: list[Attachment] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ExtractionResult:
    """Standardized extracted document content."""

    text: str = ""
    tables: list[dict[str, Any]] = field(default_factory=list)
    ocr_text: str = ""
    vlm_description: str = ""
    page_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Chunk:
    """A chunk of text ready for embedding."""

    index: int
    text: str
    char_count: int


class TextProcessor:
    """Processor for text, markdown, and CSV files."""

    def supports(self, file_type: str) -> bool:
        return file_type in {"text", "txt", "md", "csv"}

    def extract(self, file_path: str | Path) -> ExtractionResult:
        payload = extract_from_text(file_path)
        return ExtractionResult(text=payload["text"], metadata={"line_count": payload["line_count"]})


class PdfProcessor:
    """Processor for PDF files."""

    def supports(self, file_type: str) -> bool:
        return file_type == "pdf"

    def extract(self, file_path: str | Path) -> ExtractionResult:
        return extract_from_pdf(file_path)


class ImageProcessor:
    """Processor for images with OCR and optional VLM descriptions."""

    def supports(self, file_type: str) -> bool:
        return file_type in {"image", "png", "jpg", "jpeg", "bmp", "tiff", "webp"}

    def extract(self, file_path: str | Path, use_vlm: bool = True) -> ExtractionResult:
        return extract_from_image(file_path, use_vlm=use_vlm)


class MessagePreprocessor:
    """Convert text and files into a single message object."""

    def normalize(
        self,
        prompt: str,
        file: UploadFile | None = None,
    ) -> UnifiedMessage:
        content = " ".join((prompt or "").split())
        attachments: list[Attachment] = []

        if file is not None and file.filename:
            media_type = file.content_type or "application/octet-stream"
            attachments.append(
                Attachment(
                    filename=file.filename,
                    media_type=media_type,
                    kind=self._classify_attachment(media_type, file.filename),
                )
            )

        return UnifiedMessage(
            content=content,
            attachments=attachments,
            metadata={
                "attachment_count": len(attachments),
                "has_attachment": bool(attachments),
            },
        )

    def extract_local_file(
        self,
        file_path: str | Path,
        *,
        file_type: str | None = None,
        use_vlm: bool = True,
    ) -> ExtractionResult:
        """Extract structured content from a local file path."""
        path = Path(file_path)
        resolved_type = file_type or self._classify_attachment("", path.name)
        if resolved_type == "pdf":
            return extract_from_pdf(path)
        if resolved_type == "image":
            return extract_from_image(path, use_vlm=use_vlm)
        return TextProcessor().extract(path)

    @staticmethod
    def _classify_attachment(media_type: str, filename: str = "") -> str:
        if media_type.startswith("image/"):
            return "image"
        if media_type.startswith("text/"):
            return "text"
        if "pdf" in media_type:
            return "pdf"

        suffix = Path(filename).suffix.lower()
        if suffix == ".pdf":
            return "pdf"
        if suffix in {".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".webp"}:
            return "image"
        if suffix in {".txt", ".md", ".csv"}:
            return "text"
        return "file"


def clean_text(text: str) -> str:
    """Clean and normalize raw text."""
    if not text:
        return ""

    cleaned = text.replace("\r\n", "\n").replace("\r", "\n")
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    cleaned = "\n".join(line.strip() for line in cleaned.splitlines())
    cleaned = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]", "", cleaned)
    return cleaned.strip()


def extract_from_text(file_path: str | Path) -> dict[str, Any]:
    """Read and clean a text-like file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Text file not found: {path}")

    for encoding in ("utf-8", "gbk", "gb2312", "latin-1"):
        try:
            raw = path.read_text(encoding=encoding)
            break
        except (UnicodeDecodeError, LookupError):
            continue
    else:
        raise ValueError(f"Cannot decode {path.name} with any supported encoding")

    cleaned = clean_text(raw)
    line_count = len(cleaned.splitlines())
    logger.info("Text extracted: {} lines, {} chars from {}", line_count, len(cleaned), path.name)
    return {"text": cleaned, "line_count": line_count}


def extract_from_pdf(file_path: str | Path) -> ExtractionResult:
    """Extract text and tables from a PDF file."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"PDF not found: {path}")

    result = ExtractionResult()
    pages: list[dict[str, Any]] = []

    try:
        import fitz

        document = fitz.open(str(path))
        result.page_count = len(document)

        all_text: list[str] = []
        for index, page in enumerate(document):
            page_text = page.get_text("text").strip()
            if page_text:
                pages.append({"page": index + 1, "text": page_text})
                all_text.append(page_text)
        document.close()

        result.text = "\n\n".join(all_text)
        result.metadata["pages"] = pages
        logger.info("PyMuPDF extracted {} chars from {}", len(result.text), path.name)
    except Exception as exc:
        logger.warning("PyMuPDF failed for {}: {}", path.name, exc)

    try:
        import pdfplumber

        with pdfplumber.open(str(path)) as pdf:
            for index, page in enumerate(pdf.pages):
                for table in page.extract_tables():
                    if table and any(any(cell for cell in row) for row in table):
                        cleaned_table = [
                            [str(cell).strip() if cell else "" for cell in row]
                            for row in table
                        ]
                        result.tables.append({"page": index + 1, "data": cleaned_table})
        logger.info("pdfplumber extracted {} tables from {}", len(result.tables), path.name)
    except Exception as exc:
        logger.warning("pdfplumber failed for {}: {}", path.name, exc)

    if not result.text.strip():
        result.ocr_text = _ocr_pdf_pages(path)

    return result


def extract_from_image(file_path: str | Path, use_vlm: bool = True) -> ExtractionResult:
    """Extract OCR text and optional VLM description from an image."""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {path}")

    from PIL import Image

    with Image.open(path) as image:
        width, height = image.size

    result = ExtractionResult(metadata={"width": width, "height": height})
    result.ocr_text = ocr_extract(path)
    if use_vlm:
        result.vlm_description = _vlm_describe(path)
    return result


def ocr_extract(file_path: str | Path) -> str:
    """Extract text from an image file using the best available OCR backend."""
    path = Path(file_path)

    text = _ocr_via_api(path)
    if text:
        return text

    text = _ocr_via_paddle(path)
    if text:
        return text

    text = _ocr_via_tesseract(path)
    if text:
        return text

    logger.warning("No OCR text extracted from {}", path.name)
    return ""


def merge_extracted_content(
    text: str = "",
    tables: list[dict[str, Any]] | None = None,
    ocr_text: str = "",
    vlm_description: str = "",
) -> str:
    """Merge extracted content into a single embedding-ready text blob."""
    parts: list[str] = []

    if text:
        parts.append(text)

    if tables:
        for table in tables:
            page = table.get("page", "?")
            data = table.get("data", [])
            if not data:
                continue
            header = " | ".join(data[0]) if data else ""
            rows = [" | ".join(row) for row in data[1:]]
            table_text = f"[表格 - 第{page}页]\n{header}\n" + "\n".join(rows)
            parts.append(table_text)

    if ocr_text:
        parts.append(f"[图片OCR文字]\n{ocr_text}")
    if vlm_description:
        parts.append(f"[图片描述]\n{vlm_description}")

    return "\n\n".join(parts)


def chunk_text(
    text: str,
    chunk_size: int = 500,
    chunk_overlap: int = 80,
    min_chunk_size: int = 50,
) -> list[Chunk]:
    """Split text into overlapping chunks for embedding."""
    if not text or not text.strip():
        return []

    text = text.strip()
    if len(text) <= chunk_size:
        return [Chunk(index=0, text=text, char_count=len(text))]

    separators = [
        "\n\n",
        "\n",
        "。",
        "；",
        "！",
        "？",
        ". ",
        "; ",
        "，",
        ", ",
        " ",
        "",
    ]

    raw_chunks = _recursive_split(text, separators, chunk_size)
    chunks = _apply_overlap(raw_chunks, chunk_overlap)

    result: list[Chunk] = []
    for chunk in chunks:
        candidate = chunk.strip()
        if len(candidate) >= min_chunk_size:
            result.append(Chunk(index=len(result), text=candidate, char_count=len(candidate)))

    logger.info(
        "Chunked {} chars into {} chunks (size={}, overlap={})",
        len(text),
        len(result),
        chunk_size,
        chunk_overlap,
    )
    return result


def _ocr_pdf_pages(file_path: Path) -> str:
    try:
        import fitz
        import os
        import tempfile

        document = fitz.open(str(file_path))
        page_texts: list[str] = []
        for index, page in enumerate(document):
            pixmap = page.get_pixmap(dpi=150)
            image_bytes = pixmap.tobytes("png")

            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(image_bytes)
                tmp_path = tmp.name

            text = ocr_extract(tmp_path)
            os.unlink(tmp_path)

            if text:
                page_texts.append(text)
                logger.debug("OCR page {}/{}: {} chars", index + 1, len(document), len(text))

        document.close()
        return "\n\n".join(page_texts)
    except ImportError:
        logger.warning("PyMuPDF not installed, cannot render PDF pages for OCR")
        return ""
    except Exception as exc:
        logger.warning("PDF OCR failed for {}: {}", file_path.name, exc)
        return ""


def _ocr_via_api(file_path: Path) -> str:
    settings = get_settings()
    if not settings.paddleocr_api_url:
        return ""

    image_b64 = base64.b64encode(file_path.read_bytes()).decode()
    try:
        response = httpx.post(
            settings.paddleocr_api_url,
            json={"images": [image_b64]},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        lines: list[str] = []
        if "results" in data:
            for item in (data["results"] or [[]])[0]:
                text = item.get("transcription", "").strip()
                if text:
                    lines.append(text)
        elif "data" in data:
            for item in data["data"] or []:
                text = item.get("text", "").strip()
                if text:
                    lines.append(text)
        else:
            return ""

        combined = "\n".join(lines)
        if combined:
            logger.info("PaddleOCR API extracted {} chars from {}", len(combined), file_path.name)
        return combined
    except Exception as exc:
        logger.warning("PaddleOCR API failed for {}: {}", file_path.name, exc)
        return ""


def _ocr_via_paddle(file_path: Path) -> str:
    try:
        from paddleocr import PaddleOCR

        ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)
        result = ocr.ocr(str(file_path), cls=True)

        lines: list[str] = []
        if result and result[0]:
            for line in result[0]:
                text = line[1][0].strip()
                if text:
                    lines.append(text)

        combined = "\n".join(lines)
        if combined:
            logger.info("PaddleOCR local extracted {} chars from {}", len(combined), file_path.name)
        return combined
    except ImportError:
        return ""
    except Exception as exc:
        logger.warning("PaddleOCR local failed for {}: {}", file_path.name, exc)
        return ""


def _ocr_via_tesseract(file_path: Path) -> str:
    try:
        import pytesseract
        from PIL import Image

        with Image.open(file_path) as image:
            text = pytesseract.image_to_string(image, lang="chi_sim+eng").strip()
        if text:
            logger.info("Tesseract extracted {} chars from {}", len(text), file_path.name)
        return text
    except ImportError:
        return ""
    except Exception as exc:
        logger.warning("Tesseract failed for {}: {}", file_path.name, exc)
        return ""


def _vlm_describe(file_path: Path) -> str:
    try:
        from agent.llm.local_provider import vlm_describe

        return vlm_describe(file_path)
    except Exception as exc:
        logger.warning("VLM description failed for {}: {}", file_path.name, exc)
        return ""


def _recursive_split(text: str, separators: list[str], chunk_size: int) -> list[str]:
    if len(text) <= chunk_size:
        return [text]

    best_separator = ""
    for separator in separators:
        if separator == "":
            best_separator = ""
            break
        if separator in text:
            best_separator = separator
            break

    if best_separator == "":
        return [text[index : index + chunk_size] for index in range(0, len(text), chunk_size)]

    parts = text.split(best_separator)
    result: list[str] = []
    current = ""

    for part in parts:
        candidate = current + best_separator + part if current else part
        if len(candidate) <= chunk_size:
            current = candidate
            continue

        if current:
            result.append(current)
        if len(part) > chunk_size:
            remaining = separators[separators.index(best_separator) + 1 :]
            result.extend(_recursive_split(part, remaining, chunk_size))
            current = ""
        else:
            current = part

    if current:
        result.append(current)

    return result


def _apply_overlap(chunks: list[str], overlap: int) -> list[str]:
    if overlap <= 0 or len(chunks) <= 1:
        return chunks

    result = [chunks[0]]
    for index in range(1, len(chunks)):
        previous = chunks[index - 1]
        prefix = previous[-overlap:] if len(previous) > overlap else previous
        result.append(prefix + chunks[index])
    return result
