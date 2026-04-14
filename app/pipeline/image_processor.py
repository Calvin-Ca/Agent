"""Image processor — backward compatibility shim.

NOTE: This module re-exports from app.perception.image_processor.
      New code should import from app.perception.image_processor directly.
"""

from app.perception.image_processor import extract_from_image  # noqa: F401
