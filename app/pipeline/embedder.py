"""Embedder — generate vector embeddings and write to Milvus.

Uses app.model_service.embedding (local sentence-transformers or API).
"""

from __future__ import annotations

from loguru import logger

from app.db.milvus import connect_milvus, get_or_create_collection
from app.pipeline.chunker import Chunk


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
    if not chunks or not embeddings:
        return 0

    if len(chunks) != len(embeddings):
        raise ValueError(f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) length mismatch")

    connect_milvus()
    collection = get_or_create_collection()

    # Prepare insert data (must match collection schema field order)
    insert_data = [
        [project_id] * len(chunks),              # project_id
        [document_id] * len(chunks),              # document_id
        [c.index for c in chunks],                # chunk_index
        [c.text for c in chunks],                 # content
        embeddings,                               # embedding
    ]

    mr = collection.insert(insert_data)
    collection.flush()

    count = len(mr.primary_keys)
    logger.info(
        "Stored {} vectors to Milvus (project={}, doc={})",
        count, project_id, document_id,
    )
    return count


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