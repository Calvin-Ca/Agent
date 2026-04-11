"""Milvus vector database connection and collection management.

Design notes:
- Uses pymilvus ORM-style API for collection/schema definition
- Collection uses IVF_FLAT index (good balance of speed vs recall for <10M vectors)
- Partition key = project_id for efficient per-project retrieval
- For >10M vectors, switch to IVF_PQ or HNSW index
"""

from __future__ import annotations

from loguru import logger
from pymilvus import (
    Collection,
    CollectionSchema,
    DataType,
    FieldSchema,
    MilvusException,
    connections,
    utility,
)

from app.config import get_settings

_connected = False


def connect_milvus() -> None:
    """Establish connection to Milvus server."""
    global _connected
    if _connected:
        return

    settings = get_settings()
    try:
        connections.connect(
            alias="default",
            host=settings.milvus_host,
            port=settings.milvus_port,
            timeout=10,
        )
        _connected = True
        logger.info(
            "Milvus connected: {}:{}",
            settings.milvus_host,
            settings.milvus_port,
        )
    except MilvusException as e:
        logger.error("Milvus connection failed: {}", e)
        raise


def disconnect_milvus() -> None:
    """Graceful disconnect."""
    global _connected
    if _connected:
        connections.disconnect("default")
        _connected = False
        logger.info("Milvus disconnected")


def get_or_create_collection() -> Collection:
    """Get the document embeddings collection, creating it if needed.

    Schema:
        - id: int64 (auto PK)
        - project_id: varchar(64) — partition key for per-project queries
        - document_id: varchar(64)
        - chunk_index: int32
        - content: varchar(8192) — raw text chunk
        - embedding: float_vector(dim)
    """
    settings = get_settings()
    name = settings.milvus_collection
    dim = settings.milvus_dim

    connect_milvus()

    if utility.has_collection(name):
        collection = Collection(name)
        collection.load()
        logger.info("Milvus collection '{}' loaded ({} entities)", name, collection.num_entities)
        return collection

    fields = [
        FieldSchema(name="id", dtype=DataType.INT64, is_primary=True, auto_id=True),
        FieldSchema(name="project_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="document_id", dtype=DataType.VARCHAR, max_length=64),
        FieldSchema(name="chunk_index", dtype=DataType.INT32),
        FieldSchema(name="content", dtype=DataType.VARCHAR, max_length=8192),
        FieldSchema(
            name="embedding",
            dtype=DataType.FLOAT_VECTOR,
            dim=dim,
        ),
    ]
    schema = CollectionSchema(fields=fields, description="Document chunk embeddings")
    collection = Collection(name=name, schema=schema)

    # Build IVF_FLAT index — nlist=128 is reasonable for up to ~1M vectors
    index_params = {
        "metric_type": "COSINE",
        "index_type": "IVF_FLAT",
        "params": {"nlist": 128},
    }
    collection.create_index(field_name="embedding", index_params=index_params)
    collection.load()

    logger.info("Milvus collection '{}' created (dim={})", name, dim)
    return collection


def search_vectors(
    collection: Collection,
    query_embedding: list[float],
    project_id: str | None = None,
    top_k: int = 10,
    score_threshold: float = 0.5,
) -> list[dict]:
    """Search for similar document chunks.

    Returns list of dicts with keys: id, project_id, document_id, chunk_index, content, score.
    """
    search_params = {"metric_type": "COSINE", "params": {"nprobe": 16}}

    expr = f'project_id == "{project_id}"' if project_id else None

    results = collection.search(
        data=[query_embedding],
        anns_field="embedding",
        param=search_params,
        limit=top_k,
        expr=expr,
        output_fields=["project_id", "document_id", "chunk_index", "content"],
    )

    hits = []
    for hit in results[0]:
        score = hit.score
        if score < score_threshold:
            continue
        hits.append(
            {
                "id": hit.id,
                "project_id": hit.entity.get("project_id"),
                "document_id": hit.entity.get("document_id"),
                "chunk_index": hit.entity.get("chunk_index"),
                "content": hit.entity.get("content"),
                "score": round(score, 4),
            }
        )
    return hits
