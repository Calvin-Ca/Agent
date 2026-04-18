"""Memory manager — unified facade for all memory stores.

Usage:
    from app.memory.manager import memory_manager

    # Structured (MySQL)
    info = memory_manager.structured.get_project_info(project_id)

    # Vector / Long-term (Milvus)
    chunks = memory_manager.long_term.search(query, project_id)

    # Cache / Short-term (Redis)
    cached = await memory_manager.short_term.get(key)
"""

from __future__ import annotations

from app.memory.structured import StructuredMemory, structured_memory
from app.memory.long_term import VectorMemory, vector_memory
from app.memory.short_term import CacheMemory, cache_memory


class MemoryManager:
    """Facade combining structured, vector, and cache memory stores.

    Each store can be replaced independently by assigning a new
    implementation that satisfies the corresponding protocol.
    """

    def __init__(
        self,
        structured: StructuredMemory,
        long_term: VectorMemory,
        short_term: CacheMemory,
    ):
        self.structured = structured
        self.long_term = long_term
        self.short_term = short_term


# Default singleton using built-in implementations
memory_manager = MemoryManager(
    structured=structured_memory,
    long_term=vector_memory,
    short_term=cache_memory,
)
