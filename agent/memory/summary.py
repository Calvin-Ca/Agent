"""Conversation summary helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


def _normalize_content(content: str) -> str:
    return " ".join(part.strip() for part in content.splitlines() if part.strip())


@dataclass(slots=True, frozen=True)
class SummaryResult:
    """Compact summary payload returned by the summary store."""

    content: str
    source_messages: int
    truncated: bool = False


class ConversationSummaryStore:
    """Create lightweight summaries without depending on an LLM."""

    def summarize_messages(self, messages: list[dict[str, str]], max_chars: int = 400) -> SummaryResult:
        lines = []
        for message in messages:
            role = message.get("role", "user")
            content = _normalize_content(message.get("content", ""))
            if content:
                lines.append(f"{role}: {content}")
        return self._build_result(lines, max_chars=max_chars)

    def summarize_turns(self, turns: Iterable[tuple[str, str]], max_chars: int = 400) -> SummaryResult:
        lines = []
        for role, content in turns:
            normalized = _normalize_content(content)
            if normalized:
                lines.append(f"{role}: {normalized}")
        return self._build_result(lines, max_chars=max_chars)

    def _build_result(self, lines: list[str], max_chars: int) -> SummaryResult:
        if not lines:
            return SummaryResult(content="", source_messages=0, truncated=False)

        summary = "\n".join(lines)
        truncated = len(summary) > max_chars
        if truncated:
            cutoff = max(max_chars - 3, 0)
            summary = f"{summary[:cutoff].rstrip()}..."
        return SummaryResult(content=summary, source_messages=len(lines), truncated=truncated)


SummaryMemory = ConversationSummaryStore
summary_memory = ConversationSummaryStore()
