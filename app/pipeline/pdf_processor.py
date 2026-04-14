"""PDF processor — backward compatibility shim.

NOTE: This module re-exports from app.perception.pdf_processor.
      New code should import from app.perception.pdf_processor directly.
"""

from app.perception.pdf_processor import extract_from_pdf  # noqa: F401
