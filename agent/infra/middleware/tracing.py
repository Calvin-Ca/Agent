"""Tracing middleware for workflow node spans."""

from __future__ import annotations

import functools

from agent.core.context import current_context
from agent.core.state import WorkflowState
from agent.infra.middleware.base import Middleware, NodeFunc
from agent.infra.tracing import trace_span


class TracingMiddleware(Middleware):
    """Create a tracing span for each node execution."""

    def wrap(self, node_fn: NodeFunc, call_next: NodeFunc) -> NodeFunc:
        @functools.wraps(node_fn)
        def wrapper(state: WorkflowState) -> WorkflowState:
            ctx = current_context()
            with trace_span(
                f"node.{node_fn.__name__}",
                attributes={
                    "agent.node.name": node_fn.__name__,
                    "agent.project_id": state.get("project_id", ""),
                    "agent.task_type": state.get("task_type", ""),
                    "agent.tenant_id": ctx.tenant_id,
                    "agent.request_id": ctx.request_id,
                },
            ) as span:
                try:
                    result = call_next(state)
                    span.set_attribute("agent.done", result.get("done", False))
                    return result
                except Exception as exc:
                    span.record_exception(exc)
                    raise

        return wrapper


__all__ = ["TracingMiddleware"]
