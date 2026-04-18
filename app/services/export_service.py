"""Export service — convert reports to Word (.docx) or PDF.

NOTE: Now delegates to app.tools.export.
      Kept for backward compatibility with API layer.
"""

from __future__ import annotations

from app.tools.builtin.file_ops import _export_to_docx as export_to_docx  # noqa: F401
from app.tools.builtin.file_ops import _export_to_markdown as export_to_markdown  # noqa: F401
