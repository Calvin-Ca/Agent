"""Distributed tracer — OpenTelemetry integration.

TODO: Implement tracing that:
1. Creates spans for HTTP requests, DB queries, LLM calls
2. Propagates trace context across async boundaries
3. Exports to Jaeger / OTLP collector
"""

from __future__ import annotations
