"""Structured logger — request-scoped context via contextvars + loguru.

Provides:
- request_id injection into every log line within a request
- Console output (colored) + file output (plain text, daily rotation)
- Log files saved to ./logs/
"""

from __future__ import annotations

import sys
import uuid
from contextvars import ContextVar
from pathlib import Path

from loguru import logger

# ── Request-scoped context ────────────────────────────────────
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")

LOG_DIR = Path("./logs")

# Plain-text format (no ANSI colors) for file output
_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level: <8} | "
    "req:{extra[request_id]} | "
    "user:{extra[user_id]} | "
    "{name}:{function}:{line} - "
    "{message}"
)

# Colored format for console output
_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>req:{extra[request_id]}</cyan> | "
    "<blue>user:{extra[user_id]}</blue> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)


def generate_request_id() -> str:
    """Generate a short unique request ID (first 12 chars of uuid4)."""
    return uuid.uuid4().hex[:12]


def _patcher(record: dict) -> None:
    """Inject request context into every log record."""
    record["extra"]["request_id"] = request_id_var.get("-")
    record["extra"]["user_id"] = user_id_var.get("-")


def setup_logging(log_level: str = "INFO", json_output: bool = False) -> None:
    """Configure loguru with console + file handlers.

    File layout under ./logs/:
        app.log          — all logs (INFO+), daily rotation, 30 days retention
        error.log        — errors only (ERROR+), daily rotation, 60 days retention

    Args:
        log_level: Minimum log level for console output.
        json_output: If True, console outputs JSON lines (for production log aggregation).
    """
    logger.remove()  # Remove default handler

    LOG_DIR.mkdir(parents=True, exist_ok=True)

    # ── Console handler ───────────────────────────────────────
    if json_output:
        logger.add(
            sys.stdout,
            level=log_level,
            format="{message}",
            serialize=True,
        )
    else:
        logger.add(
            sys.stdout,
            level=log_level,
            format=_CONSOLE_FORMAT,
        )

    # ── File handler: all logs ────────────────────────────────
    logger.add(
        LOG_DIR / "app.log",
        level="INFO",
        format=_FILE_FORMAT,
        rotation="00:00",       # 每天午夜轮转
        retention="30 days",    # 保留 30 天
        compression="gz",       # 旧日志自动压缩
        encoding="utf-8",
        enqueue=True,           # 线程安全，异步写入不阻塞
    )

    # ── File handler: errors only ─────────────────────────────
    logger.add(
        LOG_DIR / "error.log",
        level="ERROR",
        format=_FILE_FORMAT,
        rotation="00:00",
        retention="60 days",
        compression="gz",
        encoding="utf-8",
        enqueue=True,
    )

    # Patch every log record with request context
    logger.configure(patcher=_patcher)
