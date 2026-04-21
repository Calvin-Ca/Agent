"""Streaming middleware for workflow node lifecycle events."""

from __future__ import annotations

import functools
import time

from agent.core.state import WorkflowState
from agent.infra.middleware.base import Middleware, NodeFunc
from agent.output.streaming import stream_event


class StreamingMiddleware(Middleware):
    """Emit node_start, node_end, and node_error events."""

    def wrap(self, node_fn: NodeFunc, call_next: NodeFunc) -> NodeFunc:
        @functools.wraps(node_fn)
        def wrapper(state: WorkflowState) -> WorkflowState:
            node_name = node_fn.__name__
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
                result = call_next(state)
            except Exception as exc:
                elapsed_ms = (time.perf_counter() - started_at) * 1000
                stream_event(
                    "node_error",
                    {
                        "node": node_name,
                        "error": str(exc),
                        "elapsed_ms": round(elapsed_ms),
                    },
                )
                raise

            elapsed_ms = (time.perf_counter() - started_at) * 1000
            stream_event(
                "node_end",
                {
                    "node": node_name,
                    "elapsed_ms": round(elapsed_ms),
                    "current_step": result.get("current_step", "-"),
                },
            )
            return result

        return wrapper


__all__ = ["StreamingMiddleware"]
