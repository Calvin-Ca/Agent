"""PDF processor — extract text and tables from PDF files.

Uses PyMuPDF (fitz) for text extraction, pdfplumber for tables.
Falls back gracefully if one method fails.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger

from app.pipeline.base import ExtractionResult
from app.pipeline.ocr import ocr_extract


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

    # ── OCR fallback for scanned PDFs ────────────────────────
    if not result.text.strip():
        logger.info("No selectable text in {} — running OCR on each page", file_path.name)
        result.ocr_text = _ocr_pdf_pages(file_path)

    return result


def _ocr_pdf_pages(file_path: Path) -> str:
    """Render each PDF page to an image and run OCR via app.perception.ocr."""
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(file_path))
        page_texts: list[str] = []
        for i, page in enumerate(doc):
            pix = page.get_pixmap(dpi=150)
            img_bytes = pix.tobytes("png")

            # Write to a temp file so ocr_extract can open it
            import tempfile
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                tmp.write(img_bytes)
                tmp_path = tmp.name

            text = ocr_extract(tmp_path)

            import os
            os.unlink(tmp_path)

            if text:
                page_texts.append(text)
                logger.debug("OCR page {}/{}: {} chars", i + 1, len(doc), len(text))

        doc.close()
        combined = "\n\n".join(page_texts)
        if combined:
            logger.info("PDF OCR: {} chars from {}", len(combined), file_path.name)
        return combined

    except ImportError:
        logger.warning("PyMuPDF not installed — cannot render PDF pages for OCR")
        return ""
    except Exception as e:
        logger.warning("PDF OCR failed for {}: {}", file_path.name, e)
        return ""


if __name__ == "__main__":
    pdf_path = r""
    if not pdf_path:
        raise SystemExit("Please set 'pdf_path' in pdf_processor.py before running.")

    result = extract_from_pdf(pdf_path)
    print(result)
