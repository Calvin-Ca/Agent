"""LLM cost tracker — track token usage and compute estimated costs.

TODO: Implement cost tracking that:
1. Records input/output tokens per LLM call
2. Computes cost based on model pricing
3. Aggregates per-user / per-project costs
4. Provides cost alerts when thresholds are exceeded
"""

from __future__ import annotations
