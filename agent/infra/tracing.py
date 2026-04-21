"""Distributed tracing facade with a no-op default tracer."""

from __future__ import annotations

import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Generator

from loguru import logger


class _NoOpSpan:
    def set_attribute(self, key: str, value: Any) -> None:
        return None

    def add_event(self, name: str, attributes: dict | None = None) -> None:
        return None

    def record_exception(self, exception: Exception) -> None:
        return None

    def set_status(self, status: Any, description: str = "") -> None:
        return None


class _NoOpTracer:
    @contextmanager
    def start_as_current_span(self, name: str, **kwargs) -> Generator[_NoOpSpan, None, None]:
        yield _NoOpSpan()


_tracer: _NoOpTracer | Any = _NoOpTracer()
_initialized = False

_DEFAULT_PRICING: dict[str, dict[str, float]] = {
    "deepseek-r1": {"input": 0.55, "output": 2.19},
    "deepseek-v3": {"input": 0.27, "output": 1.10},
    "qwen2.5:7b": {"input": 0.0, "output": 0.0},
    "qwen2.5:14b": {"input": 0.0, "output": 0.0},
    "qwen2.5:32b": {"input": 0.0, "output": 0.0},
    "default": {"input": 1.0, "output": 3.0},
}


@dataclass
class CostRecord:
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
    """Track token usage and estimated model costs."""

    def __init__(self, pricing: dict[str, dict[str, float]] | None = None):
        self._pricing = pricing or dict(_DEFAULT_PRICING)
        self._records: list[CostRecord] = []

    def set_pricing(self, model: str, input_per_1m: float, output_per_1m: float) -> None:
        self._pricing[model] = {"input": input_per_1m, "output": output_per_1m}

    def estimate_cost(self, model: str, prompt_tokens: int, completion_tokens: int) -> float:
        pricing = self._pricing.get(model, self._pricing["default"])
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
        record = CostRecord(
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=self.estimate_cost(model, prompt_tokens, completion_tokens),
            tenant_id=tenant_id,
            project_id=project_id,
            user_id=user_id,
            node=node,
            request_id=request_id,
        )
        self._records.append(record)
        return record

    def get_request_cost(self, request_id: str) -> float:
        return sum(record.cost_usd for record in self._records if record.request_id == request_id)

    def get_daily_cost(self, tenant_id: str = "", date: str = "") -> dict[str, Any]:
        del date
        records = self._records
        if tenant_id:
            records = [record for record in records if record.tenant_id == tenant_id]
        return {
            "total_cost_usd": round(sum(record.cost_usd for record in records), 6),
            "total_prompt_tokens": sum(record.prompt_tokens for record in records),
            "total_completion_tokens": sum(record.completion_tokens for record in records),
            "call_count": len(records),
        }

    def get_project_cost(self, project_id: str) -> dict[str, Any]:
        records = [record for record in self._records if record.project_id == project_id]
        return {
            "project_id": project_id,
            "total_cost_usd": round(sum(record.cost_usd for record in records), 6),
            "total_tokens": sum(record.prompt_tokens + record.completion_tokens for record in records),
            "call_count": len(records),
        }

    def check_budget(self, tenant_id: str, budget_usd: float) -> bool:
        daily = self.get_daily_cost(tenant_id=tenant_id)
        within_budget = daily["total_cost_usd"] <= budget_usd
        if not within_budget:
            logger.warning(
                "[CostTracker] tenant={} OVER BUDGET: ${:.4f} > ${:.4f}",
                tenant_id,
                daily["total_cost_usd"],
                budget_usd,
            )
        return within_budget


def init_tracer(
    service_name: str = "weekly-report-agent",
    endpoint: str = "",
    sample_rate: float = 1.0,
) -> None:
    """Initialize tracing infrastructure when an exporter is configured."""
    global _initialized
    if _initialized:
        return

    _initialized = True
    logger.debug(
        "[Tracer] initialized in no-op mode | service={} endpoint={} sample_rate={}",
        service_name,
        endpoint,
        sample_rate,
    )


def get_tracer() -> Any:
    """Return the configured tracer instance."""
    return _tracer


@contextmanager
def trace_span(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> Generator[Any, None, None]:
    """Create a trace span."""
    with _tracer.start_as_current_span(name) as span:
        if attributes:
            for key, value in attributes.items():
                span.set_attribute(key, value)
        yield span


cost_tracker = CostTracker()
