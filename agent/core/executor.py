"""Tool execution node placeholder for future workflow expansion."""

from __future__ import annotations

from agent.core.state import WorkflowState


def executor_node(state: WorkflowState) -> WorkflowState:
    """Execute tool calls produced by a planner step.

    This is intentionally left as a placeholder until tool-calling execution is
    wired into the current workflow graphs.
    """
    raise NotImplementedError("Executor node not yet implemented")


__all__ = ["executor_node"]
