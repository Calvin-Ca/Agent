"""Reasoning node protocol — defines the interface for all LangGraph nodes."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.agents.state import AgentState


@runtime_checkable
class ReasoningNode(Protocol):
    """Protocol for LangGraph node functions.

    Every node receives the current state and returns an updated state.
    """

    def __call__(self, state: AgentState) -> AgentState: ...
