"""Logging middleware — structured log entries for node execution.

Replaces the @log_node decorator with a chainable middleware.
"""

from __future__ import annotations

import functools
import time

from loguru import logger

from app.agents.state import AgentState
from app.agents.context import current_context
from app.agents.middleware.base import Middleware, NodeFunc


class LoggingMiddleware(Middleware):
    """Logs node entry, exit, timing, errors with structured context."""

    def wrap(self, node_fn: NodeFunc, call_next: NodeFunc) -> NodeFunc:
        @functools.wraps(node_fn)
        def wrapper(state: AgentState) -> AgentState:
            node_name = node_fn.__name__
            ctx = current_context()
            project_id = state.get("project_id", "-")
            task_type = state.get("task_type", "-")

            logger.info(
                "[Node:{}] START | req={} project={} task={} tenant={}",
                node_name, ctx.request_id, project_id, task_type, ctx.tenant_id,
            )

            start = time.perf_counter()
            try:
                result = call_next(state)
            except Exception as e:
                elapsed_ms = (time.perf_counter() - start) * 1000
                logger.error(
                    "[Node:{}] FAILED {:.0f}ms | req={} error={}",
                    node_name, elapsed_ms, ctx.request_id, e,
                )
                raise

            elapsed_ms = (time.perf_counter() - start) * 1000
            error = result.get("error", "")
            level = "warning" if error else "info"
            getattr(logger, level)(
                "[Node:{}] DONE {:.0f}ms | req={} step={} error={} done={}",
                node_name, elapsed_ms, ctx.request_id,
                result.get("current_step", "-"), error or "-", result.get("done", False),
            )
            return result

        return wrapper
