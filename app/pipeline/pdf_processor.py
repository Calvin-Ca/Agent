"""PDF processor — extract text and tables from PDF files.

Uses PyMuPDF (fitz) for text extraction, pdfplumber for tables.
Falls back gracefully if one method fails.
"""

from __future__ import annotations

from pathlib import Path

from loguru import logger


def extract_from_pdf(file_path: str | Path) -> dict:
    """Extract text and tables from a PDF file.

    Returns:
        {
            "text": "full extracted text...",
            "pages": [{"page": 1, "text": "..."}, ...],
            "tables": [{"page": 1, "data": [[...], ...]}, ...],
            "page_count": int,
        }
    """
    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"PDF not found: {file_path}")

    result = {"text": "", "pages": [], "tables": [], "page_count": 0}

    # ── PyMuPDF: text extraction ─────────────────────────────
    try:
        import fitz  # PyMuPDF

        doc = fitz.open(str(file_path))
        result["page_count"] = len(doc)

        all_text = []
        for i, page in enumerate(doc):
            page_text = page.get_text("text").strip()
            if page_text:
                result["pages"].append({"page": i + 1, "text": page_text})
                all_text.append(page_text)
        doc.close()

        result["text"] = "\n\n".join(all_text)
        logger.info("PyMuPDF: {} pages, {} chars from {}", result["page_count"], len(result["text"]), file_path.name)

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
                        result["tables"].append({"page": i + 1, "data": cleaned})

        logger.info("pdfplumber: {} tables from {}", len(result["tables"]), file_path.name)

    except Exception as e:
        logger.warning("pdfplumber failed for {}: {}", file_path.name, e)

    if not result["text"].strip():
        logger.warning("No text from {} — may be scanned PDF, consider OCR", file_path.name)

    return result