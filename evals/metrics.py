"""Evaluation metrics."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class EvalMetrics:
    total: int = 0
    passed: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0

    @property
    def accuracy(self) -> float:
        if self.total == 0:
            return 0.0
        return self.passed / self.total

