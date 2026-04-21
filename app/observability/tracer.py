"""Distributed tracer — OpenTelemetry integration for agent pipeline tracing.

Provides trace context propagation across the entire agent execution chain:
    HTTP request → Workflow → Node → LLM call → Tool call → DB query

Trace hierarchy:
    [HTTP Span]
    └── [Workflow Span] (report / query / supervisor)
        ├── [Node Span] (planner)
        ├── [Node Span] (data_collector)
        │   ├── [Tool Span] (db.get_project_info)
        │   └── [Tool Span] (vector.search_documents)
        ├── [Node Span] (report_writer)
        │   └── [LLM Span] (llm_generate)
        └── [Node Span] (report_reviewer)
            └── [LLM Span] (llm_generate)

Usage:
    from app.observability.tracer import init_tracer, get_tracer, trace_span

    # At app startup
    init_tracer(service_name="weekly-report-agent", endpoint="http://jaeger:4317")

    # In code
    tracer = get_tracer()
    with trace_span("my_operation", attributes={"key": "value"}) as span:
        result = do_work()
        span.set_attribute("result.size", len(result))

TODO: Implement when adding opentelemetry-api + opentelemetry-sdk to dependencies.
      pip install opentelemetry-api opentelemetry-sdk opentelemetry-exporter-otlp
"""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any, Generator

from loguru import logger


# ── Stub types (replaced by OTel SDK when available) ──────────────────────


class _NoOpSpan:
    """No-op span used when OpenTelemetry is not available."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def add_event(self, name: str, attributes: dict | None = None) -> None:
        pass

    def record_exception(self, exception: Exception) -> None:
        pass

    def set_status(self, status: Any, description: str = "") -> None:
        pass


class _NoOpTracer:
    """No-op tracer used when OpenTelemetry is not available."""

    @contextmanager
    def start_as_current_span(self, name: str, **kwargs) -> Generator[_NoOpSpan, None, None]:
        yield _NoOpSpan()


# ── Module state ──────────────────────────────────────────────────────────

_tracer: _NoOpTracer | Any = _NoOpTracer()
_initialized = False


# ── Public API ────────────────────────────────────────────────────────────


def init_tracer(
    service_name: str = "weekly-report-agent",
    endpoint: str = "",
    sample_rate: float = 1.0,
) -> None:
    """Initialize the OpenTelemetry tracer.

    Args:
        service_name: Service name for trace metadata.
        endpoint: OTLP collector endpoint (e.g., "http://jaeger:4317").
        sample_rate: Sampling rate (0.0 to 1.0).

    TODO: Implement with actual OTel SDK setup.
    """
    global _tracer, _initialized

    if _initialized:
        return

    # TODO: Uncomment when OTel SDK is available
    # try:
    #     from opentelemetry import trace
    #     from opentelemetry.sdk.trace import TracerProvider
    #     from opentelemetry.sdk.trace.export import BatchSpanProcessor
    #     from opentelemetry.sdk.trace.sampling import TraceIdRatioBased
    #     from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    #     from opentelemetry.sdk.resources import Resource
    #
    #     resource = Resource.create({"service.name": service_name})
    #     sampler = TraceIdRatioBased(sample_rate)
    #     provider = TracerProvider(resource=resource, sampler=sampler)
    #
    #     if endpoint:
    #         exporter = OTLPSpanExporter(endpoint=endpoint)
    #         provider.add_span_processor(BatchSpanProcessor(exporter))
    #
    #     trace.set_tracer_provider(provider)
    #     _tracer = trace.get_tracer(service_name)
    #     _initialized = True
    #     logger.info("[Tracer] initialized: service={} endpoint={}", service_name, endpoint)
    # except ImportError:
    #     logger.debug("[Tracer] opentelemetry not installed, using no-op tracer")

    _initialized = True
    logger.debug("[Tracer] initialized (no-op mode, OTel SDK not configured)")


def get_tracer() -> Any:
    """Get the configured tracer instance."""
    return _tracer


@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> Generator[Any, None, None]:
    """Create a trace span as a context manager.

    Args:
        name: Span name (e.g., "node.planner", "llm.generate").
        attributes: Key-value attributes to attach to the span.

    Yields:
        The span object (no-op if OTel is not available).
    """
    with _tracer.start_as_current_span(name) as span:
        if attributes:
            for k, v in attributes.items():
                span.set_attribute(k, v)
        yield span
