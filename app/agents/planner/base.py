"""Planner protocol — defines the interface for planner nodes."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.agents.state import AgentState


@runtime_checkable
class Planner(Protocol):
    """Protocol for planner nodes."""

    def __call__(self, state: AgentState) -> AgentState: ...
