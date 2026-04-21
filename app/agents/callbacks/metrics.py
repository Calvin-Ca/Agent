"""Metrics callback — track node latency, LLM token usage, and tool call counts.

Uses prometheus_client to expose metrics at /metrics for Prometheus scraping.
Falls back gracefully if prometheus_client is not installed.

Metrics exported:
    - agent_node_duration_seconds (Histogram): Per-node execution time
    - agent_node_errors_total (Counter): Per-node error count
    - agent_llm_tokens_total (Counter): LLM token usage (input/output)
    - agent_llm_duration_seconds (Histogram): LLM call latency
    - agent_workflow_total (Counter): Workflow invocations by task_type
    - agent_workflow_duration_seconds (Histogram): End-to-end workflow time
"""

from __future__ import annotations

import functools
import time
from typing import Callable

from loguru import logger

from app.agents.state import AgentState

try:
    from prometheus_client import Counter, Histogram

    node_duration = Histogram(
        "agent_node_duration_seconds",
        "Time spent in each LangGraph node",
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
        labelnames=["direction", "backend"],  # direction: input/output
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
    logger.debug("prometheus_client not installed, metrics collection disabled")


def is_prometheus_available() -> bool:
    return _PROMETHEUS_AVAILABLE


# ── Node metrics decorator ────────────────────────────────────


def metrics_node(func: Callable[[AgentState], AgentState]) -> Callable[[AgentState], AgentState]:
    """Decorator that records node execution duration and error counts.

    Stack with @log_node and @stream_node:
        @stream_node
        @log_node
        @metrics_node
        def my_node(state): ...
    """

    @functools.wraps(func)
    def wrapper(state: AgentState) -> AgentState:
        if not _PROMETHEUS_AVAILABLE:
            return func(state)

        node_name = func.__name__
        start = time.perf_counter()
        try:
            result = func(state)
        except Exception:
            elapsed = time.perf_counter() - start
            node_duration.labels(node=node_name).observe(elapsed)
            node_errors.labels(node=node_name).inc()
            raise

        elapsed = time.perf_counter() - start
        node_duration.labels(node=node_name).observe(elapsed)
        return result

    return wrapper


# ── LLM metrics helpers (called from model_service) ──────────


def record_llm_call(
    backend: str,
    elapsed_seconds: float,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
) -> None:
    """Record metrics for a single LLM call."""
    if not _PROMETHEUS_AVAILABLE:
        return

    llm_duration.labels(backend=backend).observe(elapsed_seconds)
    if prompt_tokens:
        llm_tokens.labels(direction="input", backend=backend).inc(prompt_tokens)
    if completion_tokens:
        llm_tokens.labels(direction="output", backend=backend).inc(completion_tokens)


def record_workflow(task_type: str, elapsed_seconds: float) -> None:
    """Record metrics for a complete workflow invocation."""
    if not _PROMETHEUS_AVAILABLE:
        return

    workflow_total.labels(task_type=task_type).inc()
    workflow_duration.labels(task_type=task_type).observe(elapsed_seconds)
