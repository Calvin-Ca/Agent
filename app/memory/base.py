"""Memory layer protocols — define the interface each store must implement.

Using Protocol (structural subtyping) so implementations don't need
to explicitly inherit; they just need to have the right methods.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class StructuredStore(Protocol):
    """Protocol for structured data access (MySQL)."""

    def get_project_info(self, project_id: str) -> dict: ...

    def get_recent_progress(self, project_id: str, weeks: int = 4) -> list[dict]: ...

    def get_recent_reports(self, project_id: str, limit: int = 3) -> list[dict]: ...

    def get_document_list(self, project_id: str) -> list[dict]: ...

    def save_report(self, **kwargs) -> str: ...


@runtime_checkable
class VectorStore(Protocol):
    """Protocol for vector similarity search (Milvus)."""

    def search(self, query: str, project_id: str, top_k: int = 8) -> list[str]: ...

    def store(self, chunks: list, embeddings: list, project_id: str, document_id: str) -> int: ...


@runtime_checkable
class CacheStore(Protocol):
    """Protocol for cache operations (Redis)."""

    async def get(self, key: str) -> Any | None: ...

    async def set(self, key: str, value: Any, ttl: int = 300) -> None: ...

    async def delete(self, key: str) -> None: ...
