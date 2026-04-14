"""Vector memory — Milvus-backed store for document embeddings.

Wraps app.db.milvus with a clean interface.
Implements VectorStore protocol.
"""

from __future__ import annotations

from loguru import logger

from app.db.milvus import connect_milvus, get_or_create_collection, search_vectors
from app.model_service.embedding import embed_texts


class VectorMemory:
    """Milvus-backed vector similarity store."""

    def search(
        self, query: str, project_id: str,
        top_k: int = 8, score_threshold: float = 0.4,
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

    def store(
        self, chunks: list, embeddings: list[list[float]],
        project_id: str, document_id: str,
    ) -> int:
        """Write chunk embeddings to Milvus.

        Args:
            chunks: List of Chunk objects (with .index, .text attrs)
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


# Singleton
vector_memory = VectorMemory()
