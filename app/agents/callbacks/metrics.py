"""Metrics callback — track latency, token usage, and tool call counts.

TODO: Implement LangGraph callback handler that:
1. Measures node execution duration
2. Counts LLM tokens (input/output)
3. Exports to Prometheus via observability.metrics
"""

from __future__ import annotations
