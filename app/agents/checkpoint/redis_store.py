"""Redis-backed checkpoint store.

Stores workflow checkpoints in Redis sorted sets, keyed by thread_id.
Each checkpoint is a JSON-serialized CheckpointRecord scored by timestamp.

TODO: Implement when integrating with the existing Redis connection in app/db/redis.py.

Redis key schema:
    checkpoint:{thread_id}        — sorted set of JSON checkpoint records
    checkpoint:index:{tenant_id}  — set of thread_ids for a tenant
"""

from __future__ import annotations

import json
import time
from typing import Any

from loguru import logger

from app.agents.checkpoint.base import CheckpointRecord, CheckpointStore


class RedisCheckpointStore:
    """Redis-backed implementation of CheckpointStore.

    Args:
        redis_client: An async-compatible Redis client (from app.db.redis).
        key_prefix: Prefix for all checkpoint keys (default: "checkpoint").
        ttl_seconds: TTL for checkpoint data (default: 7 days).

    TODO: Wire up to app.db.redis.get_redis() at startup.
    """

    def __init__(
        self,
        redis_client: Any = None,
        key_prefix: str = "checkpoint",
        ttl_seconds: int = 7 * 24 * 3600,
    ):
        self._redis = redis_client
        self._prefix = key_prefix
        self._ttl = ttl_seconds

    def _thread_key(self, thread_id: str) -> str:
        return f"{self._prefix}:{thread_id}"

    def _index_key(self, tenant_id: str) -> str:
        return f"{self._prefix}:index:{tenant_id}"

    def save(self, thread_id: str, node: str, state: dict[str, Any], **metadata) -> None:
        """Save a checkpoint to Redis.

        TODO: Implement with actual Redis calls.
        """
        record = CheckpointRecord(
            thread_id=thread_id,
            node=node,
            state=state,
            timestamp=time.time(),
            metadata=metadata,
        )
        logger.debug("[Checkpoint] save thread={} node={}", thread_id, node)
        # TODO:
        # key = self._thread_key(thread_id)
        # payload = json.dumps({"node": record.node, "state": record.state, "metadata": record.metadata})
        # self._redis.zadd(key, {payload: record.timestamp})
        # self._redis.expire(key, self._ttl)
        # if tenant_id := metadata.get("tenant_id"):
        #     self._redis.sadd(self._index_key(tenant_id), thread_id)

    def load_latest(self, thread_id: str) -> CheckpointRecord | None:
        """Load the most recent checkpoint.

        TODO: Implement with actual Redis calls.
        """
        logger.debug("[Checkpoint] load_latest thread={}", thread_id)
        # TODO:
        # key = self._thread_key(thread_id)
        # items = self._redis.zrevrange(key, 0, 0, withscores=True)
        # if not items:
        #     return None
        # payload, score = items[0]
        # data = json.loads(payload)
        # return CheckpointRecord(
        #     thread_id=thread_id, node=data["node"],
        #     state=data["state"], timestamp=score, metadata=data.get("metadata", {}),
        # )
        return None

    def load_all(self, thread_id: str) -> list[CheckpointRecord]:
        """Load all checkpoints for a thread.

        TODO: Implement with actual Redis calls.
        """
        logger.debug("[Checkpoint] load_all thread={}", thread_id)
        return []

    def delete(self, thread_id: str) -> int:
        """Delete all checkpoints for a thread.

        TODO: Implement with actual Redis calls.
        """
        logger.debug("[Checkpoint] delete thread={}", thread_id)
        return 0

    def list_threads(self, tenant_id: str = "") -> list[str]:
        """List thread IDs, optionally filtered by tenant.

        TODO: Implement with actual Redis calls.
        """
        return []
