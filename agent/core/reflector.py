"""Self-critique helpers for retries and error recovery."""

from __future__ import annotations

from agent.core.state import AgentState


class Reflector:
    """Produce operator-friendly notes when a turn fails."""

    def reflect(self, state: AgentState, error: Exception | None = None) -> list[str]:
        notes = []
        if not state.trace:
            notes.append("No reasoning trace was captured before failure.")
        if error is not None:
            notes.append(f"Last error: {error}")
        if state.intent == "query":
            notes.append("Retry with narrower retrieval scope if the answer looks noisy.")
        return notes
