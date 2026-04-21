"""Streaming middleware — push node lifecycle events to SSE / WebSocket.

Replaces the @stream_node decorator with a chainable middleware.
"""

from __future__ import annotations

import functools
import time

from app.agents.state import AgentState
from app.agents.callbacks.streaming import stream_event
from app.agents.middleware.base import Middleware, NodeFunc


class StreamingMiddleware(Middleware):
    """Emits node_start / node_end / node_error events to the stream queue."""

    def wrap(self, node_fn: NodeFunc, call_next: NodeFunc) -> NodeFunc:
        @functools.wraps(node_fn)
        def wrapper(state: AgentState) -> AgentState:
            node_name = node_fn.__name__
            project_id = state.get("project_id", "-")
            task_type = state.get("task_type", "-")

            stream_event("node_start", {
                "node": node_name,
                "project_id": project_id,
                "task_type": task_type,
            })

            start = time.perf_counter()
            try:
                result = call_next(state)
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
