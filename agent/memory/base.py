"""Memory layer protocols shared by the agent-side memory stack."""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

ConversationRole = Literal["user", "assistant", "system"]


@runtime_checkable
class StructuredStore(Protocol):
    """Protocol for structured data access backed by SQL storage."""

    def get_project_info(self, project_id: str) -> dict: ...

    def get_recent_progress(self, project_id: str, weeks: int = 4) -> list[dict]: ...

    def get_recent_reports(self, project_id: str, limit: int = 3) -> list[dict]: ...

    def get_document_list(self, project_id: str) -> list[dict]: ...

    def save_report(self, **kwargs) -> str: ...


@runtime_checkable
class VectorStore(Protocol):
    """Protocol for vector similarity search."""

    def search(self, query: str, project_id: str, top_k: int = 8) -> list[str]: ...

    def store(self, chunks: list, embeddings: list, project_id: str, document_id: str) -> int: ...


@runtime_checkable
class CacheStore(Protocol):
    """Protocol for cache operations."""

    async def get(self, key: str) -> Any | None: ...

    async def set(self, key: str, value: Any, ttl: int = 300) -> None: ...

    async def delete(self, key: str) -> None: ...


@runtime_checkable
class ConversationStore(Protocol):
    """Protocol for multi-turn conversation history."""

    def add_turn(self, session_id: str, role: ConversationRole, content: str, **metadata) -> None: ...

    def get_history(self, session_id: str, max_turns: int | None = None) -> list[Any]: ...

    def build_messages(
        self,
        session_id: str,
        system_prompt: str = "",
        max_tokens: int | None = None,
    ) -> list[dict[str, str]]: ...

    def clear_session(self, session_id: str) -> None: ...

    def summarize_and_compact(
        self,
        session_id: str,
        keep_last_turns: int = 4,
        max_summary_chars: int = 400,
    ) -> str: ...


@runtime_checkable
class EpisodicStore(Protocol):
    """Protocol for experience/episode recall."""

    def record(
        self,
        project_id: str,
        task_type: str,
        outcome: str,
        strategy: str = "",
        quality_score: float = 0.0,
        duration_seconds: float = 0.0,
        error_message: str = "",
        **context,
    ) -> str: ...

    def recall(
        self,
        project_id: str = "",
        task_type: str = "",
        query: str = "",
        outcome: str = "",
        limit: int = 5,
    ) -> list[Any]: ...


@runtime_checkable
class SummaryStore(Protocol):
    """Protocol for conversation summarization helpers."""

    def summarize_messages(self, messages: list[dict[str, str]], max_chars: int = 400) -> Any: ...

    def summarize_turns(self, turns: list[tuple[str, str]], max_chars: int = 400) -> Any: ...
