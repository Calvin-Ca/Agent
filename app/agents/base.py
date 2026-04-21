"""Agent base protocols — define the interface for workflows.

Every workflow (report, query, supervisor, ...) implements the Workflow protocol.
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


@runtime_checkable
class AsyncWorkflow(Protocol):
    """Protocol for async LangGraph-based workflows.

    Prefer this for new workflows to enable proper async execution
    with checkpointing and streaming.
    """

    def build(self) -> Any:
        """Build and return a compiled LangGraph."""
        ...

    async def arun(self, **kwargs) -> dict:
        """Execute the workflow asynchronously and return results."""
        ...


@runtime_checkable
class ResumableWorkflow(Protocol):
    """Protocol for workflows that support checkpoint-based resumption.

    Extends the base Workflow with thread_id tracking for resume capability.
    """

    def build(self) -> Any:
        """Build and return a compiled LangGraph with checkpointer."""
        ...

    def run(self, **kwargs) -> dict:
        """Execute the workflow and return results."""
        ...

    def resume(self, thread_id: str, **kwargs) -> dict:
        """Resume a previously interrupted workflow from its last checkpoint.

        Args:
            thread_id: The thread ID of the interrupted execution.
            **kwargs: Additional parameters to override on resume.

        Returns:
            Same result format as run().
        """
        ...
