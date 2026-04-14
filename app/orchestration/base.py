"""Orchestration layer protocols — define the interface for workflows.

Every workflow (report, query, ...) implements the Workflow protocol.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class Workflow(Protocol):
    """Protocol for LangGraph-based workflows."""

    def build(self) -> Any:
        """Build and return a compiled LangGraph."""
        ...

    def run(self, **kwargs) -> dict:
        """Execute the workflow and return results."""
        ...
