"""Redis async connection pool with cache and lock helpers.

Provides:
- Connection pool (high-concurrency safe)
- get / set / delete cache helpers with JSON serialization
- Distributed lock for deduplicating expensive tasks (e.g. report generation)
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from typing import Any

import redis.asyncio as aioredis

from app.config import get_settings

_pool: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Get or create the global Redis connection pool."""
    global _pool
    if _pool is None:
        settings = get_settings()
        _pool = aioredis.from_url(
            settings.redis_url,
            decode_responses=True,
            max_connections=50,
            socket_connect_timeout=5,
            socket_keepalive=True,
            retry_on_timeout=True,
        )
    return _pool


async def close_redis() -> None:
    """Graceful shutdown."""
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


# ── Cache Helpers ────────────────────────────────────────────


async def cache_get(key: str) -> Any | None:
    """Get a cached value, returns deserialized JSON or None."""
    r = get_redis()
    raw = await r.get(key)
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return raw


async def cache_set(key: str, value: Any, ttl: int = 300) -> None:
    """Set a cached value with TTL (default 5 min)."""
    r = get_redis()
    serialized = json.dumps(value, ensure_ascii=False, default=str)
    await r.set(key, serialized, ex=ttl)


async def cache_delete(key: str) -> None:
    """Delete a cached key."""
    r = get_redis()
    await r.delete(key)


async def cache_delete_pattern(pattern: str) -> int:
    """Delete all keys matching a glob pattern. Returns count deleted."""
    r = get_redis()
    count = 0
    async for key in r.scan_iter(match=pattern, count=200):
        await r.delete(key)
        count += 1
    return count


# ── Distributed Lock ────────────────────────────────────────


@asynccontextmanager
async def distributed_lock(
    name: str,
    timeout: int = 60,
    blocking_timeout: int = 5,
) -> AsyncGenerator[bool, None]:
    """Acquire a Redis-based distributed lock.

    Usage:
        async with distributed_lock("report:proj_123") as acquired:
            if acquired:
                # do expensive work
            else:
                # another worker is already doing it
    """
    r = get_redis()
    lock = r.lock(f"lock:{name}", timeout=timeout, blocking_timeout=blocking_timeout)
    acquired = False
    try:
        acquired = await lock.acquire()
        yield acquired
    finally:
        if acquired:
            try:
                await lock.release()
            except aioredis.exceptions.LockNotOwnedError:
                pass  # lock expired before we released
