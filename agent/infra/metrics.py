"""Prometheus metrics for HTTP and agent workflow execution."""

from __future__ import annotations

import functools
import time
from typing import Callable

from loguru import logger

try:
    from prometheus_client import Counter, Histogram, make_asgi_app

    http_request_duration = Histogram(
        "http_request_duration_seconds",
        "HTTP request latency",
        labelnames=["method", "path", "status"],
        buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
    )
    http_requests_total = Counter(
        "http_requests_total",
        "Total HTTP request count",
        labelnames=["method", "path", "status"],
    )
    node_duration = Histogram(
        "agent_node_duration_seconds",
        "Time spent in each workflow node",
        labelnames=["node"],
        buckets=(0.1, 0.5, 1, 2, 5, 10, 30, 60, 120),
    )
    node_errors = Counter(
        "agent_node_errors_total",
        "Number of node execution errors",
        labelnames=["node"],
    )
    llm_tokens = Counter(
        "agent_llm_tokens_total",
        "LLM token usage",
        labelnames=["direction", "backend"],
    )
    llm_duration = Histogram(
        "agent_llm_duration_seconds",
        "LLM call latency",
        labelnames=["backend"],
        buckets=(0.5, 1, 2, 5, 10, 30, 60, 120),
    )
    workflow_total = Counter(
        "agent_workflow_total",
        "Number of workflow invocations",
        labelnames=["task_type"],
    )
    workflow_duration = Histogram(
        "agent_workflow_duration_seconds",
        "End-to-end workflow execution time",
        labelnames=["task_type"],
        buckets=(1, 5, 10, 30, 60, 120, 300),
    )
    _PROMETHEUS_AVAILABLE = True
except ImportError:
    _PROMETHEUS_AVAILABLE = False
    logger.debug("prometheus_client not installed, metrics disabled")


def make_metrics_app():
    """Return a mountable Prometheus ASGI app when available."""
    if not _PROMETHEUS_AVAILABLE:
        return None
    return make_asgi_app()


def record_http_request(method: str, path: str, status: int, elapsed_seconds: float) -> None:
    """Record HTTP latency and request counts."""
    if not _PROMETHEUS_AVAILABLE:
        return
    labels = {"method": method, "path": path, "status": str(status)}
    http_requests_total.labels(**labels).inc()
    http_request_duration.labels(**labels).observe(elapsed_seconds)


def metrics_node(func: Callable):
    """Decorator that records node execution duration and errors."""
    @functools.wraps(func)
    def wrapper(state):
        if not _PROMETHEUS_AVAILABLE:
            return func(state)

        node_name = func.__name__
        started_at = time.perf_counter()
        try:
            result = func(state)
        except Exception:
            node_duration.labels(node=node_name).observe(time.perf_counter() - started_at)
            node_errors.labels(node=node_name).inc()
            raise

        node_duration.labels(node=node_name).observe(time.perf_counter() - started_at)
        return result

    return wrapper


def record_llm_call(
    backend: str,
    elapsed_seconds: float,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """Record latency and token usage for a single LLM call."""
    if not _PROMETHEUS_AVAILABLE:
        return

    llm_duration.labels(backend=backend).observe(elapsed_seconds)
    if prompt_tokens:
        llm_tokens.labels(direction="input", backend=backend).inc(prompt_tokens)
    if completion_tokens:
        llm_tokens.labels(direction="output", backend=backend).inc(completion_tokens)


def record_workflow(task_type: str, elapsed_seconds: float) -> None:
    """Record workflow-level latency and counts."""
    if not _PROMETHEUS_AVAILABLE:
        return
    workflow_total.labels(task_type=task_type).inc()
    workflow_duration.labels(task_type=task_type).observe(elapsed_seconds)
