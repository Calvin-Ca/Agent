"""Prometheus-backed metrics middleware for workflow nodes."""

from __future__ import annotations

import functools
import time

from agent.core.context import current_context
from agent.core.state import WorkflowState
from agent.infra.middleware.base import Middleware, NodeFunc

try:
    from prometheus_client import Counter, Histogram

    _node_duration = Histogram(
        "agent_mw_node_duration_seconds",
        "Node execution time (middleware-tracked)",
        labelnames=["node", "tenant"],
        buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120),
    )
    _node_errors = Counter(
        "agent_mw_node_errors_total",
        "Node error count (middleware-tracked)",
        labelnames=["node", "tenant"],
    )
    _PROM = True
except ImportError:
    _PROM = False


class MetricsMiddleware(Middleware):
    """Record per-node execution duration and error counts."""

    def wrap(self, node_fn: NodeFunc, call_next: NodeFunc) -> NodeFunc:
        if not _PROM:
            return call_next

        @functools.wraps(node_fn)
        def wrapper(state: WorkflowState) -> WorkflowState:
            node_name = node_fn.__name__
            tenant = current_context().tenant_id or "default"
            started_at = time.perf_counter()

            try:
                result = call_next(state)
            except Exception:
                _node_duration.labels(node=node_name, tenant=tenant).observe(time.perf_counter() - started_at)
                _node_errors.labels(node=node_name, tenant=tenant).inc()
                raise

            _node_duration.labels(node=node_name, tenant=tenant).observe(time.perf_counter() - started_at)
            return result

        return wrapper


__all__ = ["MetricsMiddleware"]
