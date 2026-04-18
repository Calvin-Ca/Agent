"""Short-term memory — Redis-backed store for session caching and distributed locks.

TTL-based ephemeral storage for session history, intermediate results.
Implements CacheStore protocol.
"""

from __future__ import annotations

from typing import Any

from app.db.redis import cache_get, cache_set, cache_delete, cache_delete_pattern, distributed_lock


class CacheMemory:
    """Redis-backed cache store."""

    async def get(self, key: str) -> Any | None:
        """Get a cached value, returns deserialized JSON or None."""
        return await cache_get(key)

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        """Set a cached value with TTL (default 5 min)."""
        await cache_set(key, value, ttl=ttl)

    async def delete(self, key: str) -> None:
        """Delete a cached key."""
        await cache_delete(key)

    async def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a glob pattern. Returns count deleted."""
        return await cache_delete_pattern(pattern)

    def lock(self, name: str, timeout: int = 60, blocking_timeout: int = 5):
        """Acquire a Redis-based distributed lock (async context manager)."""
        return distributed_lock(name, timeout=timeout, blocking_timeout=blocking_timeout)


# Singleton
cache_memory = CacheMemory()
