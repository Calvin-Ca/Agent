"""LLM cost tracker — token usage accounting and cost estimation.

Tracks per-request, per-user, and per-project LLM token consumption
and estimated costs. Enables:
- Real-time cost visibility per workflow execution
- Per-tenant cost aggregation and budgeting
- Cost alerts when thresholds are exceeded
- Model cost comparison and optimization

Pricing is configurable per model. Costs are stored in Redis for
real-time aggregation and MySQL for historical analysis.

Usage:
    from app.observability.cost_tracker import cost_tracker

    # Record a single LLM call
    cost_tracker.record(
        model="deepseek-r1",
        prompt_tokens=1500,
        completion_tokens=800,
        tenant_id="tenant-001",
        project_id="proj-001",
        node="report_writer",
    )

    # Query costs
    daily = cost_tracker.get_daily_cost(tenant_id="tenant-001")
    project = cost_tracker.get_project_cost(project_id="proj-001")

TODO: Implement with Redis (real-time) + MySQL (historical) backends.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from loguru import logger


# ── Model pricing (USD per 1M tokens) ────────────────────────────────────

_DEFAULT_PRICING: dict[str, dict[str, float]] = {
    # model_name: {"input": price_per_1M, "output": price_per_1M}
    "deepseek-r1": {"input": 0.55, "output": 2.19},
    "deepseek-v3": {"input": 0.27, "output": 1.10},
    "qwen2.5:7b": {"input": 0.0, "output": 0.0},  # Local model, no API cost
    "qwen2.5:14b": {"input": 0.0, "output": 0.0},
    "qwen2.5:32b": {"input": 0.0, "output": 0.0},
    "default": {"input": 1.0, "output": 3.0},  # Fallback pricing
}


@dataclass
class CostRecord:
    """A single LLM cost record."""

    model: str
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    tenant_id: str = ""
    project_id: str = ""
    user_id: str = ""
    node: str = ""
    request_id: str = ""
    timestamp: float = field(default_factory=time.time)


class CostTracker:
    """Tracks and aggregates LLM token usage and costs.

    TODO: Wire up to Redis and MySQL for persistent storage.
    """

    def __init__(self, pricing: dict[str, dict[str, float]] | None = None):
        self._pricing = pricing or dict(_DEFAULT_PRICING)
        # In-memory accumulator (replaced by Redis in production)
        self._records: list[CostRecord] = []

    def set_pricing(self, model: str, input_per_1m: float, output_per_1m: float) -> None:
        """Set or update pricing for a model."""
        self._pricing[model] = {"input": input_per_1m, "output": output_per_1m}

    def estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        """Estimate cost for a single LLM call.

        Returns:
            Estimated cost in USD.
        """
        pricing = self._pricing.get(model, self._pricing.get("default", {"input": 0, "output": 0}))
        input_cost = (prompt_tokens / 1_000_000) * pricing["input"]
        output_cost = (completion_tokens / 1_000_000) * pricing["output"]
        return input_cost + output_cost

    def record(
        self,
        model: str,
        prompt_tokens: int,
        completion_tokens: int,
        tenant_id: str = "",
        project_id: str = "",
        user_id: str = "",
        node: str = "",
        request_id: str = "",
    ) -> CostRecord:
        """Record token usage for a single LLM call.

        Returns:
            The created CostRecord with calculated cost.

        TODO: Persist to Redis (real-time counter) + async write to MySQL.
        """
        cost = self.estimate_cost(model, prompt_tokens, completion_tokens)

        rec = CostRecord(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
            tenant_id=tenant_id,
            project_id=project_id,
            user_id=user_id,
            node=node,
            request_id=request_id,
        )
        self._records.append(rec)

        logger.debug(
            "[CostTracker] model={} in={} out={} cost=${:.6f} tenant={} project={}",
            model, prompt_tokens, completion_tokens, cost, tenant_id, project_id,
        )
        return rec

    def get_request_cost(self, request_id: str) -> float:
        """Get total cost for a single request/workflow execution.

        TODO: Query from Redis.
        """
        return sum(r.cost_usd for r in self._records if r.request_id == request_id)

    def get_daily_cost(self, tenant_id: str = "", date: str = "") -> dict[str, Any]:
        """Get aggregated daily cost summary.

        Returns:
            {"total_cost_usd": float, "total_tokens": int, "call_count": int, ...}

        TODO: Query from Redis/MySQL.
        """
        records = self._records
        if tenant_id:
            records = [r for r in records if r.tenant_id == tenant_id]

        return {
            "total_cost_usd": round(sum(r.cost_usd for r in records), 6),
            "total_prompt_tokens": sum(r.prompt_tokens for r in records),
            "total_completion_tokens": sum(r.completion_tokens for r in records),
            "call_count": len(records),
        }

    def get_project_cost(self, project_id: str) -> dict[str, Any]:
        """Get aggregated cost for a project.

        TODO: Query from MySQL for historical data.
        """
        records = [r for r in self._records if r.project_id == project_id]
        return {
            "project_id": project_id,
            "total_cost_usd": round(sum(r.cost_usd for r in records), 6),
            "total_tokens": sum(r.prompt_tokens + r.completion_tokens for r in records),
            "call_count": len(records),
        }

    def check_budget(self, tenant_id: str, budget_usd: float) -> bool:
        """Check if a tenant has exceeded their budget.

        Returns:
            True if within budget, False if exceeded.

        TODO: Implement with Redis counter for real-time checking.
        """
        daily = self.get_daily_cost(tenant_id=tenant_id)
        within = daily["total_cost_usd"] <= budget_usd
        if not within:
            logger.warning(
                "[CostTracker] tenant={} OVER BUDGET: ${:.4f} > ${:.4f}",
                tenant_id, daily["total_cost_usd"], budget_usd,
            )
        return within


# Singleton
cost_tracker = CostTracker()
