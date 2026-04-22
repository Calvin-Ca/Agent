"""SSE and partial-response helpers."""

from __future__ import annotations

import asyncio
import functools
import json
import time
from contextvars import ContextVar, Token
from typing import TYPE_CHECKING, Any

from fastapi import UploadFile
from loguru import logger

if TYPE_CHECKING:
    from agent.core.agent_loop import AgentLoop


def sse_event(event: str, data: Any) -> str:
    """Format a server-sent event frame."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class ResponseStreamer:
    """Bridge the agent loop to SSE clients."""

    def __init__(self, agent_loop: AgentLoop) -> None:
        self.agent_loop = agent_loop

    async def stream_chat(
        self,
        *,
        db: Any,
        user: Any,
        prompt: str,
        file: UploadFile | None = None,
    ):
        state = await self.agent_loop.prepare_state(
            prompt=prompt,
            file=file,
            user_id=str(user.id),
        )

        yield sse_event(
            "intent",
            {
                "intent": state.intent,
                "params": state.params,
                "plan": [step.name for step in state.plan],
            },
        )

        try:
            result = await self.agent_loop.handle_chat(
                db=db,
                user=user,
                prompt=prompt,
                file=file,
                state=state,
            )
        except Exception as exc:
            yield sse_event("error", {"message": str(exc), "reflections": state.reflections})
            return

        payload = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
        yield sse_event("result", payload)
        yield sse_event("done", {"status": "completed"})


_stream_queue_var: ContextVar[asyncio.Queue | None] = ContextVar("stream_queue", default=None)


def set_stream_queue(queue: asyncio.Queue) -> Token:
    """Bind a stream queue for the current context."""
    return _stream_queue_var.set(queue)


def reset_stream_queue(token: Token) -> None:
    """Reset the bound stream queue."""
    _stream_queue_var.reset(token)


def get_stream_queue() -> asyncio.Queue | None:
    """Get the currently bound stream queue."""
    return _stream_queue_var.get(None)


def stream_event(event_type: str, data: dict[str, Any] | None = None) -> None:
    """Push an event to the bound stream queue."""
    queue = _stream_queue_var.get(None)
    if queue is None:
        return

    event = {"type": event_type}
    if data:
        event.update(data)

    try:
        queue.put_nowait(event)
    except asyncio.QueueFull:
        logger.warning("[Stream] Queue full, dropping event {}", event_type)


def stream_node(func):
    """Decorator that emits node_start / node_end / node_error events."""
    @functools.wraps(func)
    def wrapper(state):
        node_name = func.__name__
        stream_event(
            "node_start",
            {
                "node": node_name,
                "project_id": state.get("project_id", "-"),
                "task_type": state.get("task_type", "-"),
            },
        )

        started_at = time.perf_counter()
        try:
            result = func(state)
        except Exception as exc:
            stream_event(
                "node_error",
                {"node": node_name, "error": str(exc), "elapsed_ms": round((time.perf_counter() - started_at) * 1000)},
            )
            raise

        stream_event(
            "node_end",
            {
                "node": node_name,
                "elapsed_ms": round((time.perf_counter() - started_at) * 1000),
                "current_step": result.get("current_step", "-"),
            },
        )
        return result

    return wrapper
