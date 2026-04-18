"""Application metrics — Prometheus counters, histograms, gauges.

TODO: Implement metrics that:
1. Track agent_latency_seconds (histogram)
2. Count tool_call_total, llm_tokens_used
3. Expose /metrics endpoint for Prometheus scraping
"""

from __future__ import annotations
