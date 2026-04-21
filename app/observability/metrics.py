"""Application metrics — Prometheus counters, histograms, gauges.

Exposes metrics collected by app.agents.callbacks.metrics at /metrics.
Falls back gracefully if prometheus_client is not installed.

Mount the ASGI app in main.py:
    from app.observability.metrics import make_metrics_app
    metrics_app = make_metrics_app()
    if metrics_app:
        app.mount("/metrics", metrics_app)

Metrics defined here:
    http_request_duration_seconds  — HTTP request latency by method/path/status
    http_requests_total            — HTTP request count by method/path/status

Agent-specific metrics are defined in app.agents.callbacks.metrics.
"""

from __future__ import annotations

from loguru import logger

try:
    from prometheus_client import Counter, Histogram, make_asgi_app, REGISTRY

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

    _PROMETHEUS_AVAILABLE = True

except ImportError:
    _PROMETHEUS_AVAILABLE = False
    logger.debug("prometheus_client not installed, /metrics endpoint disabled")


def make_metrics_app():
    """Return a Prometheus ASGI app suitable for mounting at /metrics.

    Returns None if prometheus_client is not installed.
    """
    if not _PROMETHEUS_AVAILABLE:
        return None
    return make_asgi_app()


def record_http_request(method: str, path: str, status: int, elapsed_seconds: float) -> None:
    """Record HTTP request metrics (called from middleware)."""
    if not _PROMETHEUS_AVAILABLE:
        return
    label = {"method": method, "path": path, "status": str(status)}
    http_requests_total.labels(**label).inc()
    http_request_duration.labels(**label).observe(elapsed_seconds)
