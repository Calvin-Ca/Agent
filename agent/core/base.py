"""Workflow and node protocols for the agent runtime."""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from agent.core.state import WorkflowState


@runtime_checkable
class Workflow(Protocol):
    """Protocol for sync workflows."""

    def build(self) -> Any:
        """Build and return the compiled workflow graph."""
        ...

    def run(self, **kwargs) -> dict:
        """Execute the workflow and return a result payload."""
        ...


@runtime_checkable
class AsyncWorkflow(Protocol):
    """Protocol for async workflows."""

    def build(self) -> Any:
        """Build and return the compiled workflow graph."""
        ...

    async def arun(self, **kwargs) -> dict:
        """Execute the workflow asynchronously and return a result payload."""
        ...


@runtime_checkable
class ResumableWorkflow(Protocol):
    """Protocol for workflows that support checkpoint-based resume."""

    def build(self) -> Any:
        """Build and return the compiled workflow graph."""
        ...

    def run(self, **kwargs) -> dict:
        """Execute the workflow and return a result payload."""
        ...

    def resume(self, thread_id: str, **kwargs) -> dict:
        """Resume a previously interrupted workflow."""
        ...


@runtime_checkable
class ReasoningNode(Protocol):
    """Protocol for workflow node callables."""

    def __call__(self, state: WorkflowState) -> WorkflowState:
        ...


__all__ = ["AsyncWorkflow", "ReasoningNode", "ResumableWorkflow", "Workflow"]
