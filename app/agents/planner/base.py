"""Planner base — abstract interface for all planner implementations.

A planner is responsible for:
  1. Validating the initial state (project_id, user_input, etc.)
  2. Inferring / confirming task_type when not explicitly supplied
  3. Pre-computing shared fields (week_start, retry_count) so downstream
     nodes don't need to repeat the logic.

To implement a custom planner, subclass BasePlanner and override
``plan()``.  Register it via the graph builder instead of DefaultPlanner.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.agents.state import AgentState


class BasePlanner(ABC):
    """Abstract base class for all planners."""

    @abstractmethod
    def plan(self, state: AgentState) -> AgentState:
        """Validate and prepare *state* for downstream nodes.

        Args:
            state: The current workflow state dict.

        Returns:
            An updated state dict.  On validation failure the returned dict
            must contain ``error`` (non-empty str) and ``done=True``.
        """
        ...

    # ── convenience helpers ────────────────────────────────────────────────

    def _fail(self, state: AgentState, message: str) -> AgentState:
        """Return a terminal error state."""
        return {**state, "error": message, "done": True}
