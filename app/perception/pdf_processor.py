"""PDF processor — extract text and tables from PDF files.

Uses PyMuPDF (fitz) for text extraction, pdfplumber for tables.
Falls back gracefully if one method fails.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from app.perception.base import ExtractionResult


class PdfProcessor:
    """PDF document processor."""

    def supports(self, file_type: str) -> bool:
        return file_type in ("pdf",)

    def extract(self, file_path: str) -> ExtractionResult:
        """Extract text and tables from a PDF file."""
        return extract_from_pdf(file_path)


def extract_from_pdf(file_path: str | Path) -> ExtractionResult:
    """Extract text and tables from a PDF file.

    Returns:
        ExtractionResult with text, tables, and page_count
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    result = ExtractionResult()
    pages = []

    # ── PyMuPDF: text extraction ─────────────────────────────
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(file_path))
        result.page_count = len(doc)

        all_text = []
        for i, page in enumerate(doc):
            page_text = page.get_text("text").strip()
            if page_text:
                pages.append({"page": i + 1, "text": page_text})
                all_text.append(page_text)
        doc.close()

        result.text = "\n\n".join(all_text)
        result.metadata["pages"] = pages
        logger.info("PyMuPDF: {} pages, {} chars from {}", result.page_count, len(result.text), file_path.name)

    except Exception as e:
        logger.warning("PyMuPDF failed for {}: {}", file_path.name, e)

    # ── pdfplumber: table extraction ─────────────────────────
    try:
        import pdfplumber

        with pdfplumber.open(str(file_path)) as pdf:
            for i, page in enumerate(pdf.pages):
                for table in page.extract_tables():
                    if table and any(any(cell for cell in row) for row in table):
                        cleaned = [
                            [str(cell).strip() if cell else "" for cell in row]
                            for row in table
                        ]
                        result.tables.append({"page": i + 1, "data": cleaned})

        logger.info("pdfplumber: {} tables from {}", len(result.tables), file_path.name)

    except Exception as e:
        logger.warning("pdfplumber failed for {}: {}", file_path.name, e)

    if not result.text.strip():
        logger.warning("No text from {} — may be scanned PDF, consider OCR", file_path.name)

    return result
