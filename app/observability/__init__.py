"""Observability package — logging, metrics, tracing, and cost tracking.

Components:
    - logger: Structured logging with loguru (request-scoped context)
    - metrics: Prometheus metrics for HTTP and agent pipelines
    - tracer: OpenTelemetry distributed tracing (TODO: full implementation)
    - cost_tracker: LLM token usage accounting and cost estimation
"""

from app.observability.logger import (
    setup_logging,
    request_log_scope,
    run_in_executor_with_context,
    generate_request_id,
    get_log_context,
)
from app.observability.metrics import make_metrics_app, record_http_request
from app.observability.tracer import init_tracer, get_tracer, trace_span
from app.observability.cost_tracker import cost_tracker

__all__ = [
    # Logging
    "setup_logging",
    "request_log_scope",
    "run_in_executor_with_context",
    "generate_request_id",
    "get_log_context",
    # Metrics
    "make_metrics_app",
    "record_http_request",
    # Tracing
    "init_tracer",
    "get_tracer",
    "trace_span",
    # Cost
    "cost_tracker",
]
