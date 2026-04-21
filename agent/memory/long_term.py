"""Long-term vector memory backed by Milvus."""

from __future__ import annotations

from loguru import logger

from agent.llm.local_provider import embed_texts
from app.db.milvus import connect_milvus, get_or_create_collection, search_vectors


class LongTermMemoryStore:
    """Milvus-backed vector similarity store."""

    def search(
        self,
        query: str,
        project_id: str,
        top_k: int = 8,
        score_threshold: float = 0.4,
    ) -> list[str]:
        if not query.strip():
            return []

        embeddings = embed_texts([query])
        if not embeddings or not embeddings[0]:
            logger.warning("Failed to generate query embedding")
            return []

        connect_milvus()
        collection = get_or_create_collection()
        results = search_vectors(
            collection,
            query_embedding=embeddings[0],
            project_id=project_id,
            top_k=top_k,
            score_threshold=score_threshold,
        )
        chunks = [item["content"] for item in results if item.get("content")]
        logger.info("Vector search '{}' -> {} results", query[:30], len(chunks))
        return chunks

    def store(
        self,
        chunks: list,
        embeddings: list[list[float]],
        project_id: str,
        document_id: str,
    ) -> int:
        if not chunks or not embeddings:
            return 0
        if len(chunks) != len(embeddings):
            raise ValueError(f"chunks ({len(chunks)}) and embeddings ({len(embeddings)}) length mismatch")

        connect_milvus()
        collection = get_or_create_collection()
        insert_data = [
            [project_id] * len(chunks),
            [document_id] * len(chunks),
            [chunk.index for chunk in chunks],
            [chunk.text for chunk in chunks],
            embeddings,
        ]
        mutation_result = collection.insert(insert_data)
        collection.flush()
        return len(mutation_result.primary_keys)

    def write(self, chunks: list, embeddings: list[list[float]], project_id: str, document_id: str) -> int:
        return self.store(chunks=chunks, embeddings=embeddings, project_id=project_id, document_id=document_id)


VectorMemory = LongTermMemoryStore
vector_memory = LongTermMemoryStore()
