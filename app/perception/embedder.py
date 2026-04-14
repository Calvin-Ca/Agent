"""Embedder — generate vector embeddings and write to Milvus.

Uses app.model_service.embedding (local sentence-transformers or API).
"""

from __future__ import annotations

from loguru import logger

from app.perception.chunker import Chunk
from app.memory.vector import vector_memory


def embed_texts(texts: list[str], batch_size: int | None = None) -> list[list[float]]:
    """Generate embeddings via model_service (local or API).

    Args:
        texts: List of text strings to embed
        batch_size: Override default batch size

    Returns:
        List of embedding vectors
    """
    from app.model_service.embedding import embed_texts as _embed
    return _embed(texts, batch_size=batch_size)


def store_chunks_to_milvus(
    chunks: list[Chunk],
    embeddings: list[list[float]],
    project_id: str,
    document_id: str,
) -> int:
    """Write chunk embeddings to Milvus.

    Args:
        chunks: List of Chunk objects
        embeddings: Corresponding embedding vectors
        project_id: Project ID for partition filtering
        document_id: Source document ID

    Returns:
        Number of vectors inserted
    """
    return vector_memory.store(chunks, embeddings, project_id, document_id)


def embed_and_store(
    chunks: list[Chunk],
    project_id: str,
    document_id: str,
) -> int:
    """Convenience: embed chunks and store to Milvus in one call."""
    if not chunks:
        return 0

    texts = [c.text for c in chunks]
    embeddings = embed_texts(texts)
    return store_chunks_to_milvus(chunks, embeddings, project_id, document_id)
