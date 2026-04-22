"""Redis-backed checkpoint store."""

from __future__ import annotations

import time
from typing import Any

from loguru import logger

from agent.checkpoint.base import CheckpointRecord, CheckpointStore


class RedisCheckpointStore:
    """Redis-backed implementation of ``CheckpointStore``.

    The current implementation keeps the public contract in the agent layer and
    leaves backend wiring for a later iteration.
    """

    def __init__(
        self,
        redis_client: Any = None,
        key_prefix: str = "checkpoint",
        ttl_seconds: int = 7 * 24 * 3600,
    ) -> None:
        self._redis = redis_client
        self._prefix = key_prefix
        self._ttl = ttl_seconds

    def _thread_key(self, thread_id: str) -> str:
        return f"{self._prefix}:{thread_id}"

    def _index_key(self, tenant_id: str) -> str:
        return f"{self._prefix}:index:{tenant_id}"

    def save(self, thread_id: str, node: str, state: dict[str, Any], **metadata) -> None:
        record = CheckpointRecord(
            thread_id=thread_id,
            node=node,
            state=state,
            timestamp=time.time(),
            metadata=metadata,
        )
        logger.debug("[Checkpoint] save thread={} node={}", thread_id, node)
        _ = record

    def load_latest(self, thread_id: str) -> CheckpointRecord | None:
        logger.debug("[Checkpoint] load_latest thread={}", thread_id)
        return None

    def load_all(self, thread_id: str) -> list[CheckpointRecord]:
        logger.debug("[Checkpoint] load_all thread={}", thread_id)
        return []

    def delete(self, thread_id: str) -> int:
        logger.debug("[Checkpoint] delete thread={}", thread_id)
        return 0

    def list_threads(self, tenant_id: str = "") -> list[str]:
        _ = tenant_id
        return []


__all__ = ["CheckpointStore", "RedisCheckpointStore"]
