"""Smart text chunker — backward compatibility shim.

NOTE: This module re-exports from app.perception.chunker.
      New code should import from app.perception.chunker directly.
"""

from app.perception.chunker import Chunk, chunk_text  # noqa: F401
