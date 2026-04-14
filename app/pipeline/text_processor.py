"""Text processor — backward compatibility shim.

NOTE: This module re-exports from app.perception.text_processor.
      New code should import from app.perception.text_processor directly.
"""

from app.perception.text_processor import (  # noqa: F401
    extract_from_text,
    clean_text,
    merge_extracted_content,
)
