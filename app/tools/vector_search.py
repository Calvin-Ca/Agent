"""Tool: Milvus vector search — retrieve relevant document chunks.

Used by agent nodes to find context from uploaded documents via RAG.
"""

from __future__ import annotations

from loguru import logger

from app.db.milvus import connect_milvus, get_or_create_collection, search_vectors
from app.model_service.embedding import embed_texts
from app.tools.base import BaseTool, ToolResult


# ═══════════════════════════════════════════════════════════════
# Internal search helpers (preserved from original code)
# ═══════════════════════════════════════════════════════════════


def _search_documents(
    query: str,
    project_id: str,
    top_k: int = 8,
    score_threshold: float = 0.4,
) -> list[str]:
    """Search for relevant document chunks using semantic similarity.

    Args:
        query: Natural language query
        project_id: Filter to specific project
        top_k: Max results to return
        score_threshold: Minimum similarity score

    Returns:
        List of relevant text chunks, sorted by relevance
    """
    if not query.strip():
        return []

    # Generate query embedding
    embeddings = embed_texts([query])
    if not embeddings or not embeddings[0]:
        logger.warning("Failed to generate query embedding")
        return []

    query_embedding = embeddings[0]

    # Search Milvus
    connect_milvus()
    collection = get_or_create_collection()

    results = search_vectors(
        collection,
        query_embedding=query_embedding,
        project_id=project_id,
        top_k=top_k,
        score_threshold=score_threshold,
    )

    chunks = [r["content"] for r in results if r.get("content")]
    logger.info(
        "Vector search: '{}...' → {} results (project={})",
        query[:30], len(chunks), project_id,
    )
    return chunks


def _search_multi_queries(
    queries: list[str],
    project_id: str,
    top_k_per_query: int = 5,
    score_threshold: float = 0.4,
) -> list[str]:
    """Search with multiple queries and deduplicate results.

    Useful when the agent generates multiple search angles.
    """
    all_chunks = []
    seen = set()

    for q in queries:
        chunks = _search_documents(
            q, project_id,
            top_k=top_k_per_query,
            score_threshold=score_threshold,
        )
        for chunk in chunks:
            chunk_key = chunk[:100]  # dedup by first 100 chars
            if chunk_key not in seen:
                seen.add(chunk_key)
                all_chunks.append(chunk)

    logger.info("Multi-query search: {} queries → {} unique chunks", len(queries), len(all_chunks))
    return all_chunks


# ═══════════════════════════════════════════════════════════════
# Tool classes (registry-compatible wrappers)
# ═══════════════════════════════════════════════════════════════


class VectorSearchTool(BaseTool):
    """Search for relevant document chunks using semantic similarity."""

    @property
    def name(self) -> str:
        return "vector.search_documents"

    @property
    def description(self) -> str:
        return "Search for relevant document chunks using semantic similarity in Milvus"

    def execute(
        self, *, query: str, project_id: str,
        top_k: int = 8, score_threshold: float = 0.4, **kwargs,
    ) -> ToolResult:
        try:
            chunks = _search_documents(query, project_id, top_k=top_k, score_threshold=score_threshold)
            return ToolResult(success=True, data=chunks, metadata={"count": len(chunks)})
        except Exception as e:
            return ToolResult(success=False, data=[], error=str(e))


class MultiQuerySearchTool(BaseTool):
    """Search with multiple queries and deduplicate results."""

    @property
    def name(self) -> str:
        return "vector.search_multi"

    @property
    def description(self) -> str:
        return "Search with multiple queries and deduplicate results"

    def execute(
        self, *, queries: list[str], project_id: str,
        top_k_per_query: int = 5, score_threshold: float = 0.4, **kwargs,
    ) -> ToolResult:
        try:
            chunks = _search_multi_queries(queries, project_id, top_k_per_query, score_threshold)
            return ToolResult(success=True, data=chunks, metadata={"count": len(chunks)})
        except Exception as e:
            return ToolResult(success=False, data=[], error=str(e))
