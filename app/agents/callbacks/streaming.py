"""Streaming callback — push node events to SSE / WebSocket connections.

Provides a context-based streaming mechanism:
1. Set a stream queue via `set_stream_queue()` before invoking the graph
2. Nodes and LLM calls push events to the queue
3. The WebSocket / SSE endpoint reads from the queue and forwards to client

Usage:
    from app.agents.callbacks.streaming import set_stream_queue, stream_event, get_stream_queue

    queue = asyncio.Queue()
    token = set_stream_queue(queue)
    try:
        # run graph in executor ...
        # inside nodes, call stream_event("node_start", {...})
    finally:
        reset_stream_queue(token)
"""

from __future__ import annotations

import asyncio
import functools
from contextvars import ContextVar, Token
from typing import Any, Callable

from loguru import logger

from app.agents.state import AgentState

# ── Stream queue context ──────────────────────────────────────
_stream_queue_var: ContextVar[asyncio.Queue | None] = ContextVar("stream_queue", default=None)


def set_stream_queue(queue: asyncio.Queue) -> Token:
    """Bind a stream queue for the current context (request scope)."""
    return _stream_queue_var.set(queue)


def reset_stream_queue(token: Token) -> None:
    """Reset the stream queue after the request is done."""
    _stream_queue_var.reset(token)


def get_stream_queue() -> asyncio.Queue | None:
    """Get the current stream queue, or None if not in a streaming context."""
    return _stream_queue_var.get(None)


def stream_event(event_type: str, data: dict[str, Any] | None = None) -> None:
    """Push an event to the stream queue (non-blocking, fire-and-forget).

    Event types:
        - node_start: {node, project_id, task_type}
        - node_end:   {node, elapsed_ms, current_step}
        - node_error: {node, error, elapsed_ms}
        - llm_start:  {node}
        - llm_end:    {node, output_chars, elapsed_ms}
        - token:      {content}
        - done:       {report_id, title}
        - error:      {message}

    Safe to call outside of a streaming context — silently no-ops.
    """
    queue = _stream_queue_var.get(None)
    if queue is None:
        return

    event = {"type": event_type}
    if data:
        event.update(data)

    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        logger.warning("[Stream] Queue full, dropping event: {}", event_type)


def stream_node(func: Callable[[AgentState], AgentState]) -> Callable[[AgentState], AgentState]:
    """Decorator that emits node_start / node_end / node_error stream events.

    Can be stacked with @log_node. Put @stream_node on the outside (first decorator)
    so it wraps the logged execution.

    Example:
        @stream_node
        @log_node
        def my_node(state: AgentState) -> AgentState: ...
    """
    import time

    @functools.wraps(func)
    def wrapper(state: AgentState) -> AgentState:
        node_name = func.__name__
        project_id = state.get("project_id", "-")
        task_type = state.get("task_type", "-")

        stream_event("node_start", {
            "node": node_name,
            "project_id": project_id,
            "task_type": task_type,
        })

        start = time.perf_counter()
        try:
            result = func(state)
        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            stream_event("node_error", {
                "node": node_name,
                "error": str(e),
                "elapsed_ms": round(elapsed_ms),
            })
            raise

        elapsed_ms = (time.perf_counter() - start) * 1000
        stream_event("node_end", {
            "node": node_name,
            "elapsed_ms": round(elapsed_ms),
            "current_step": result.get("current_step", "-"),
        })

        return result

    return wrapper
