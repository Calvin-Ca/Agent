"""Metrics middleware — Prometheus histograms and counters for node execution.

Replaces the @metrics_node decorator with a chainable middleware.
"""

from __future__ import annotations

import functools
import time

from app.agents.state import AgentState
from app.agents.middleware.base import Middleware, NodeFunc

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
    """Records per-node execution duration and error counts via Prometheus."""

    def wrap(self, node_fn: NodeFunc, call_next: NodeFunc) -> NodeFunc:
        if not _PROM:
            return call_next

        @functools.wraps(node_fn)
        def wrapper(state: AgentState) -> AgentState:
            from app.agents.context import current_context

            node_name = node_fn.__name__
            tenant = current_context().tenant_id or "default"
            start = time.perf_counter()
            try:
                result = call_next(state)
            except Exception:
                elapsed = time.perf_counter() - start
                _node_duration.labels(node=node_name, tenant=tenant).observe(elapsed)
                _node_errors.labels(node=node_name, tenant=tenant).inc()
                raise

            elapsed = time.perf_counter() - start
            _node_duration.labels(node=node_name, tenant=tenant).observe(elapsed)
            return result

        return wrapper
