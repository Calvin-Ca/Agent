"""Tool: Milvus vector search — retrieve relevant document chunks.

Used by agent nodes to find context from uploaded documents via RAG.

NOTE: This module re-exports from app.tools.vector_search for backward compatibility.
      New code should use tool_registry.execute("vector.*") instead.
"""

from app.tools.vector_search import (  # noqa: F401
    _search_documents as search_documents,
    _search_multi_queries as search_multi_queries,
)
