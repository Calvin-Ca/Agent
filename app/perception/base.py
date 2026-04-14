"""Perception layer protocols — define the interface for document processors.

Each file type (PDF, image, text) has its own processor that implements
the DocumentProcessor protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class ExtractionResult:
    """Standardized output from any document processor."""

    text: str = ""
    tables: list[dict] = field(default_factory=list)
    ocr_text: str = ""
    vlm_description: str = ""
    page_count: int = 0
    metadata: dict = field(default_factory=dict)


@runtime_checkable
class DocumentProcessor(Protocol):
    """Protocol for document content extraction."""

    def extract(self, file_path: str) -> ExtractionResult:
        """Extract content from a document file."""
        ...

    def supports(self, file_type: str) -> bool:
        """Check if this processor supports the given file type."""
        ...
