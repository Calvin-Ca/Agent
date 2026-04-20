"""Structured logger — request-scoped context via contextvars + loguru.

Provides:
- request_id injection into every log line within a request
- Console output (colored) + file output (plain text, daily rotation)
- Per-request logs saved to ./logs/{request_file}.log
- Helpers to propagate log context across threads / Celery tasks
"""

from __future__ import annotations

import sys
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from functools import partial
from pathlib import Path

from loguru import logger

# ── Request-scoped context ────────────────────────────────────
request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")
request_log_file_var: ContextVar[str] = ContextVar("request_log_file", default="")

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


def build_request_log_filename(rid: str, inv_ts: int) -> str:
    """Build the request log filename from inverted timestamp + request ID."""
    return f"{inv_ts}_{rid[:8]}.log"


def get_log_context() -> dict[str, str]:
    """Return the current request-scoped log context."""
    return {
        "request_id": request_id_var.get("-"),
        "user_id": user_id_var.get("-"),
        "request_log_file": request_log_file_var.get(""),
    }


def _patcher(record: dict) -> None:
    """Inject request context into every log record."""
    record["extra"]["request_id"] = request_id_var.get("-")
    record["extra"]["user_id"] = user_id_var.get("-")


def setup_logging(log_level: str = "INFO", json_output: bool = False) -> None:
    """Configure loguru with console handlers and request-scoped file sinks.

    Request middleware adds a temporary per-request sink so each request gets
    its own log file under ``./logs/``.

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

    # Patch every log record with request context
    logger.configure(patcher=_patcher)


def add_request_sink(rid: str, request_log_file: str) -> int:
    """Add a per-request sink filtered by request ID.

    Args:
        rid: The request ID used to filter log records.
        request_log_file: Request log filename under ``./logs/``.

    Returns:
        Loguru sink ID to remove after the request finishes.
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _request_filter(record: dict) -> bool:
        return record["extra"].get("request_id") == rid

    return logger.add(
        LOG_DIR / request_log_file,
        level="DEBUG",
        format=_FILE_FORMAT,
        filter=_request_filter,
        encoding="utf-8",
        enqueue=True,
    )


def remove_request_sink(sink_id: int) -> None:
    """Remove the per-request sink after the request completes."""
    try:
        logger.remove(sink_id)
    except ValueError:
        pass


@contextmanager
def request_log_scope(request_id: str, user_id: str = "-", request_log_file: str = "") -> Iterator[None]:
    """Bind request log context and optionally attach a request sink."""
    request_id_token = request_id_var.set(request_id or "-")
    user_id_token = user_id_var.set(user_id or "-")
    request_log_file_token = request_log_file_var.set(request_log_file or "")
    sink_id: int | None = None

    if request_id and request_id != "-" and request_log_file:
        sink_id = add_request_sink(request_id, request_log_file)

    try:
        yield
    finally:
        if sink_id is not None:
            remove_request_sink(sink_id)
        request_log_file_var.reset(request_log_file_token)
        user_id_var.reset(user_id_token)
        request_id_var.reset(request_id_token)


async def run_in_executor_with_context(loop, func: Callable, *args):
    """Run a blocking callable in the executor while preserving contextvars."""
    ctx = copy_context()
    return await loop.run_in_executor(None, partial(ctx.run, func, *args))
