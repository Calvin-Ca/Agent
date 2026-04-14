"""Embedder — backward compatibility shim.

NOTE: This module re-exports from app.perception.embedder.
      New code should import from app.perception.embedder directly.
"""

from app.perception.embedder import (  # noqa: F401
    embed_texts,
    store_chunks_to_milvus,
    embed_and_store,
)
