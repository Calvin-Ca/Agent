"""Checkpoint store protocol — defines the interface for state persistence.

Any backend (Redis, SQLite, PostgreSQL) can implement this protocol
to provide checkpoint/resume capability for LangGraph workflows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable
import time


@dataclass
class CheckpointRecord:
    """A single checkpoint snapshot.

    Attributes:
        thread_id: Unique identifier for the workflow execution.
        node: The node that just completed when this checkpoint was saved.
        state: The full AgentState dict at checkpoint time.
        timestamp: Unix timestamp of the checkpoint.
        metadata: Extra context (tenant_id, user_id, etc.).
    """

    thread_id: str
    node: str
    state: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class CheckpointStore(Protocol):
    """Protocol for checkpoint persistence backends."""

    def save(self, thread_id: str, node: str, state: dict[str, Any], **metadata) -> None:
        """Save a checkpoint after a node completes.

        Args:
            thread_id: Workflow execution identifier.
            node: Name of the node that just completed.
            state: Full AgentState dict.
            **metadata: Additional metadata (tenant_id, user_id, etc.).
        """
        ...

    def load_latest(self, thread_id: str) -> CheckpointRecord | None:
        """Load the most recent checkpoint for a thread.

        Returns:
            The latest CheckpointRecord, or None if no checkpoints exist.
        """
        ...

    def load_all(self, thread_id: str) -> list[CheckpointRecord]:
        """Load all checkpoints for a thread, ordered by timestamp ascending.

        Returns:
            List of CheckpointRecord instances.
        """
        ...

    def delete(self, thread_id: str) -> int:
        """Delete all checkpoints for a thread.

        Returns:
            Number of checkpoints deleted.
        """
        ...

    def list_threads(self, tenant_id: str = "") -> list[str]:
        """List all thread IDs, optionally filtered by tenant.

        Returns:
            List of thread_id strings.
        """
        ...
