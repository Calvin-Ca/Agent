"""Checkpoint store protocol for workflow state persistence."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class CheckpointRecord:
    """A single checkpoint snapshot."""

    thread_id: str
    node: str
    state: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class CheckpointStore(Protocol):
    """Protocol for checkpoint persistence backends."""

    def save(self, thread_id: str, node: str, state: dict[str, Any], **metadata) -> None:
        ...

    def load_latest(self, thread_id: str) -> CheckpointRecord | None:
        ...

    def load_all(self, thread_id: str) -> list[CheckpointRecord]:
        ...

    def delete(self, thread_id: str) -> int:
        ...

    def list_threads(self, tenant_id: str = "") -> list[str]:
        ...


__all__ = ["CheckpointRecord", "CheckpointStore"]
