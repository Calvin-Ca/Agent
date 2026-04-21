"""Agent middleware — composable pipeline for cross-cutting concerns.

Replaces the stacked-decorator pattern (@stream_node, @log_node, @metrics_node)
with a chainable middleware architecture. Existing decorators in callbacks/
remain for backward compatibility.

Usage:
    from app.agents.middleware import MiddlewareChain, LoggingMiddleware, MetricsMiddleware

    chain = MiddlewareChain([
        LoggingMiddleware(),
        MetricsMiddleware(),
        TracingMiddleware(),
        RetryMiddleware(max_retries=2),
        StreamingMiddleware(),
    ])

    # Wrap a node function
    wrapped_node = chain.wrap(my_node)

    # Or apply to all nodes in a workflow
    chain.apply_to_graph(graph_builder)
"""

from app.agents.middleware.base import Middleware, MiddlewareChain, NodeFunc
from app.agents.middleware.logging import LoggingMiddleware
from app.agents.middleware.metrics import MetricsMiddleware
from app.agents.middleware.streaming import StreamingMiddleware
from app.agents.middleware.tracing import TracingMiddleware
from app.agents.middleware.retry import RetryMiddleware

__all__ = [
    "Middleware",
    "MiddlewareChain",
    "NodeFunc",
    "LoggingMiddleware",
    "MetricsMiddleware",
    "StreamingMiddleware",
    "TracingMiddleware",
    "RetryMiddleware",
]
