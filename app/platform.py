"""Platform-level REST endpoints (no version prefix, no auth).

/health  — liveness probe (always responds if process is up)
/ready   — readiness probe (checks all downstream dependencies)
/info    — build & runtime metadata

All business interactions are served via /api/v1/agent/stream (SSE).
"""

from __future__ import annotations

import time
from typing import Annotated

from fastapi import APIRouter, Depends
from loguru import logger

from app.core.response import R
from app.dependencies import AppContainer, get_container

router = APIRouter(tags=["platform"])

# ── 启动时间戳，在模块加载时记录 ─────────────────────────────
_started_at: float = time.time()


# ── Liveness ─────────────────────────────────────────────────


@router.get("/health", summary="存活检查")
async def health() -> R:
    """K8s liveness probe — 只要进程活着就返回 200。"""
    return R.ok(data={"status": "alive"})


# ── Readiness ────────────────────────────────────────────────


async def _check_mysql() -> dict:
    """Ping MySQL via a lightweight query."""
    from app.db.mysql import _get_engine

    engine = _get_engine()
    try:
        async with engine.connect() as conn:
            await conn.execute(__import__("sqlalchemy").text("SELECT 1"))
        return {"mysql": "ok"}
    except Exception as exc:
        return {"mysql": f"error: {exc}"}


async def _check_redis() -> dict:
    """Ping Redis."""
    from app.db.redis import get_redis

    try:
        r = get_redis()
        await r.ping()
        return {"redis": "ok"}
    except Exception as exc:
        return {"redis": f"error: {exc}"}


def _check_milvus() -> dict:
    """Check Milvus connection state."""
    from app.db.milvus import _connected

    return {"milvus": "ok" if _connected else "disconnected"}


def _check_minio() -> dict:
    """Try listing buckets on MinIO."""
    from app.db.minio import _get_client

    try:
        _get_client().list_buckets()
        return {"minio": "ok"}
    except Exception as exc:
        return {"minio": f"error: {exc}"}


@router.get("/ready", summary="就绪检查")
async def ready() -> R:
    """K8s readiness probe — 检查所有下游依赖是否可用。

    任何一个依赖不可用时返回 code=50300，但仍是 HTTP 200
    （由调用方根据 code 字段判断是否就绪）。
    """
    checks: dict[str, str] = {}

    # MySQL & Redis are async
    checks.update(await _check_mysql())
    checks.update(await _check_redis())

    # Milvus & MinIO are sync checks
    checks.update(_check_milvus())
    checks.update(_check_minio())

    all_ok = all(v == "ok" for v in checks.values())

    if not all_ok:
        logger.warning("Readiness check partial failure: {}", checks)

    return R.ok(data={"ready": all_ok, "checks": checks}) if all_ok else R.fail(
        code=50300,
        message="部分依赖不可用",
        data={"ready": False, "checks": checks},
    )


# ── Info ─────────────────────────────────────────────────────


def _git_commit() -> str:
    """Best-effort read of current git commit hash."""
    import subprocess

    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
                timeout=3,
            )
            .decode()
            .strip()
        )
    except Exception:
        return "unknown"


@router.get("/info", summary="运行时信息")
async def info(
    container: Annotated[AppContainer, Depends(get_container)],
) -> R:
    """返回构建和运行时元数据，供前端 / 运维使用。"""
    import sys

    settings = container.settings
    uptime_seconds = round(time.time() - _started_at)

    return R.ok(
        data={
            "app": settings.app_name,
            "env": settings.app_env,
            "debug": settings.debug,
            "python": sys.version.split()[0],
            "commit": _git_commit(),
            "uptime_seconds": uptime_seconds,
            "backend": settings.backend,
            "llm_model": settings.llm_model_name,
            "embed_model": settings.embed_model_name,
        }
    )
