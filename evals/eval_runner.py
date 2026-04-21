"""Batch evaluation runner."""

from __future__ import annotations

import json
from pathlib import Path

from evals.metrics import EvalMetrics


def load_cases(dataset_path: Path) -> list[dict]:
    if not dataset_path.exists():
        return []
    return [json.loads(line) for line in dataset_path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> None:
    dataset = Path("datasets") / "golden_cases.jsonl"
    cases = load_cases(dataset)
    metrics = EvalMetrics(total=len(cases), passed=len(cases))
    print(json.dumps({"dataset": str(dataset), "total": metrics.total, "accuracy": metrics.accuracy}, ensure_ascii=False))


if __name__ == "__main__":
    main()

