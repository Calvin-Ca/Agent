"""SSE streaming and workflow event helpers.

Enterprise SSE event protocol:
    connected   — session acknowledged, carries conversation_id
    thinking    — agent processing stage (intent recognition, planning, etc.)
    intent      — recognized intent with params and execution plan
    node_start  — workflow node begins execution
    node_end    — workflow node completed
    node_error  — workflow node failed
    token       — incremental content chunk for streaming LLM output
    result      — final structured response
    error       — error with optional reflections
    done        — stream complete, carries timing metadata
"""

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
    """Format a single server-sent event frame."""
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


class ResponseStreamer:
    """Bridge the agent loop to SSE clients with rich event protocol."""

    def __init__(self, agent_loop: AgentLoop) -> None:
        self.agent_loop = agent_loop

    async def stream_chat(
        self,
        *,
        db: Any,
        user: Any,
        prompt: str,
        file: UploadFile | None = None,
        conversation_id: str = "",
    ):
        """Async generator that yields SSE events throughout the agent lifecycle."""
        started_at = time.perf_counter()

        # ── connected ────────────────────────────────────────────
        yield sse_event("connected", {
            "conversation_id": conversation_id,
            "user_id": str(user.id),
        })

        # ── thinking: intent recognition ─────────────────────────
        yield sse_event("thinking", {"stage": "intent_recognition"})

        try:
            state = await self.agent_loop.prepare_state(
                prompt=prompt,
                file=file,
                user_id=str(user.id),
            )
        except Exception as exc:
            yield sse_event("error", {
                "stage": "intent_recognition",
                "message": str(exc),
            })
            return

        # ── intent ───────────────────────────────────────────────
        yield sse_event("intent", {
            "intent": state.intent,
            "params": state.params,
            "plan": [step.name for step in state.plan],
            "confidence": state.metadata.get("confidence", 1.0),
        })

        # ── thinking: execution ──────────────────────────────────
        yield sse_event("thinking", {"stage": "execution"})

        # Bind a stream queue so workflow nodes can push events
        queue: asyncio.Queue = asyncio.Queue(maxsize=512)
        queue_token = set_stream_queue(queue)

        try:
            # Launch execution as a task so we can drain queue concurrently
            exec_task = asyncio.create_task(
                self.agent_loop.handle_chat(
                    db=db,
                    user=user,
                    prompt=prompt,
                    file=file,
                    state=state,
                )
            )

            # Forward workflow node events while execution is running
            async for event in _drain_queue(queue, exec_task):
                yield sse_event(event["type"], {k: v for k, v in event.items() if k != "type"})

            # Await the execution result
            result = exec_task.result()

        except Exception as exc:
            yield sse_event("error", {
                "stage": "execution",
                "message": str(exc),
                "reflections": state.reflections,
                "trace": state.trace[-3:] if state.trace else [],
            })
            return
        finally:
            reset_stream_queue(queue_token)

        # ── result ───────────────────────────────────────────────
        payload = result.model_dump(mode="json") if hasattr(result, "model_dump") else result
        yield sse_event("result", payload)

        # ── done ─────────────────────────────────────────────────
        elapsed_ms = round((time.perf_counter() - started_at) * 1000)
        yield sse_event("done", {
            "status": "completed",
            "conversation_id": conversation_id,
            "elapsed_ms": elapsed_ms,
        })


async def _drain_queue(queue: asyncio.Queue, task: asyncio.Task) -> Any:
    """Yield events from the queue until the task completes."""
    while not task.done():
        try:
            event = await asyncio.wait_for(queue.get(), timeout=0.1)
            if isinstance(event, dict):
                yield event
        except asyncio.TimeoutError:
            continue

    # Drain any remaining events after task completion
    while not queue.empty():
        event = queue.get_nowait()
        if isinstance(event, dict):
            yield event


# ── Context-var based stream queue ───────────────────────────────

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
    """Push an event to the bound stream queue (called from workflow nodes)."""
    queue = _stream_queue_var.get(None)
    if queue is None:
        return

    event: dict[str, Any] = {"type": event_type}
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
                {
                    "node": node_name,
                    "error": str(exc),
                    "elapsed_ms": round((time.perf_counter() - started_at) * 1000),
                },
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
