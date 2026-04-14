"""Unified memory facade — single entry point for all memory stores.

Usage:
    from app.memory.unified import unified_memory

    # Structured (MySQL)
    info = unified_memory.structured.get_project_info(project_id)

    # Vector (Milvus)
    chunks = unified_memory.vector.search(query, project_id)

    # Cache (Redis)
    cached = await unified_memory.cache.get(key)
"""

from __future__ import annotations

from app.memory.structured import StructuredMemory, structured_memory
from app.memory.vector import VectorMemory, vector_memory
from app.memory.cache import CacheMemory, cache_memory


class UnifiedMemory:
    """Facade combining structured, vector, and cache memory stores.

    Each store can be replaced independently by assigning a new
    implementation that satisfies the corresponding protocol.
    """

    def __init__(
        self,
        structured: StructuredMemory,
        vector: VectorMemory,
        cache: CacheMemory,
    ):
        self.structured = structured
        self.vector = vector
        self.cache = cache


# Default singleton using built-in implementations
unified_memory = UnifiedMemory(
    structured=structured_memory,
    vector=vector_memory,
    cache=cache_memory,
)
