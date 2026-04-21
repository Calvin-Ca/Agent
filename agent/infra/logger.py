"""Structured logging helpers with request-scoped context."""

from __future__ import annotations

import asyncio
import functools
import sys
import time
import uuid
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar, copy_context
from functools import partial
from pathlib import Path

from loguru import logger

request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
user_id_var: ContextVar[str] = ContextVar("user_id", default="-")
request_log_file_var: ContextVar[str] = ContextVar("request_log_file", default="")

LOG_DIR = Path("./logs")

_FILE_FORMAT = (
    "{time:YYYY-MM-DD HH:mm:ss.SSS} | "
    "{level: <8} | "
    "req:{extra[request_id]} | "
    "user:{extra[user_id]} | "
    "{name}:{function}:{line} - "
    "{message}"
)

_CONSOLE_FORMAT = (
    "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
    "<level>{level: <8}</level> | "
    "<cyan>req:{extra[request_id]}</cyan> | "
    "<blue>user:{extra[user_id]}</blue> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)


def generate_request_id() -> str:
    """Generate a short unique request identifier."""
    return uuid.uuid4().hex[:12]


def build_request_log_filename(request_id: str, inverted_timestamp: int) -> str:
    """Build a request-scoped log filename."""
    return f"{inverted_timestamp}_{request_id[:8]}.log"


def get_log_context() -> dict[str, str]:
    """Return the current request-scoped log context."""
    return {
        "request_id": request_id_var.get("-"),
        "user_id": user_id_var.get("-"),
        "request_log_file": request_log_file_var.get(""),
    }


def _patcher(record: dict) -> None:
    record["extra"]["request_id"] = request_id_var.get("-")
    record["extra"]["user_id"] = user_id_var.get("-")


def setup_logging(log_level: str = "INFO", json_output: bool = False) -> None:
    """Configure loguru handlers for console and request-scoped files."""
    logger.remove()
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    if json_output:
        logger.add(sys.stdout, level=log_level, format="{message}", serialize=True)
    else:
        logger.add(sys.stdout, level=log_level, format=_CONSOLE_FORMAT)

    logger.configure(patcher=_patcher)


def add_request_sink(request_id: str, request_log_file: str) -> int:
    """Attach a per-request log sink."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    def _request_filter(record: dict) -> bool:
        return record["extra"].get("request_id") == request_id

    return logger.add(
        LOG_DIR / request_log_file,
        level="DEBUG",
        format=_FILE_FORMAT,
        filter=_request_filter,
        encoding="utf-8",
        enqueue=True,
    )


def remove_request_sink(sink_id: int) -> None:
    """Remove a request-scoped sink."""
    try:
        logger.remove(sink_id)
    except ValueError:
        pass


@contextmanager
def request_log_scope(request_id: str, user_id: str = "-", request_log_file: str = "") -> Iterator[None]:
    """Bind request context and optionally create a request-scoped sink."""
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
    """Run a blocking callable while preserving contextvars."""
    context = copy_context()
    return await loop.run_in_executor(None, partial(context.run, func, *args))


def log_node(func: Callable):
    """Decorator that logs node entry, exit, timing, and errors."""
    if asyncio.iscoroutinefunction(func):
        return _async_log_node(func)
    return _sync_log_node(func)


def _sync_log_node(func: Callable):
    @functools.wraps(func)
    def wrapper(state):
        node_name = func.__name__
        project_id = state.get("project_id", "-")
        task_type = state.get("task_type", "-")
        previous_step = state.get("current_step", "-")

        logger.info(
            "[Node:{}] START | project={} task={} prev_step={}",
            node_name,
            project_id,
            task_type,
            previous_step,
        )

        started_at = time.perf_counter()
        try:
            result = func(state)
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            logger.error("[Node:{}] FAILED after {:.0f}ms | error={}", node_name, elapsed_ms, exc)
            raise

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.info(
            "[Node:{}] DONE {:.0f}ms | step={} done={} error={}",
            node_name,
            elapsed_ms,
            result.get("current_step", "-"),
            result.get("done", False),
            result.get("error", ""),
        )
        return result

    return wrapper


def _async_log_node(func: Callable):
    @functools.wraps(func)
    async def wrapper(state):
        node_name = func.__name__
        project_id = state.get("project_id", "-")
        task_type = state.get("task_type", "-")
        previous_step = state.get("current_step", "-")

        logger.info(
            "[Node:{}] START | project={} task={} prev_step={}",
            node_name,
            project_id,
            task_type,
            previous_step,
        )

        started_at = time.perf_counter()
        try:
            result = await func(state)
        except Exception as exc:
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            logger.error("[Node:{}] FAILED after {:.0f}ms | error={}", node_name, elapsed_ms, exc)
            raise

        elapsed_ms = (time.perf_counter() - started_at) * 1000
        logger.info(
            "[Node:{}] DONE {:.0f}ms | step={} done={} error={}",
            node_name,
            elapsed_ms,
            result.get("current_step", "-"),
            result.get("done", False),
            result.get("error", ""),
        )
        return result

    return wrapper
