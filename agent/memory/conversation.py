"""Conversation memory for session-scoped multi-turn history."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Literal

from loguru import logger

from agent.memory.summary import ConversationSummaryStore, summary_memory


@dataclass(slots=True)
class ConversationTurn:
    """A single conversational turn."""

    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    token_count: int = 0

    def to_message(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


class ConversationMemoryStore:
    """Session-scoped conversation history with basic token budgeting."""

    def __init__(
        self,
        max_turns: int = 20,
        max_tokens: int = 8000,
        ttl_seconds: int = 3600,
        summary_store: ConversationSummaryStore | None = None,
    ) -> None:
        if max_turns <= 0:
            raise ValueError("max_turns must be positive")
        if max_tokens <= 0:
            raise ValueError("max_tokens must be positive")

        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self.ttl_seconds = ttl_seconds
        self.summary_store = summary_store or summary_memory
        self._sessions: dict[str, deque[ConversationTurn]] = {}

    def add_turn(
        self,
        session_id: str,
        role: Literal["user", "assistant", "system"],
        content: str,
        **metadata,
    ) -> None:
        """Append a turn to the session history."""
        if not session_id:
            raise ValueError("session_id is required")

        turn = ConversationTurn(
            role=role,
            content=content,
            metadata=metadata,
            token_count=self._estimate_tokens(content),
        )
        session = self._get_or_create_session(session_id)
        session.append(turn)
        logger.debug("[ConversationMemory] add_turn session={} role={} chars={}", session_id, role, len(content))

    def get_history(self, session_id: str, max_turns: int | None = None) -> list[ConversationTurn]:
        """Return conversation turns ordered from oldest to newest."""
        turns = list(self._sessions.get(session_id, ()))
        if max_turns is None or max_turns >= len(turns):
            return turns
        return turns[-max_turns:]

    def build_messages(
        self,
        session_id: str,
        system_prompt: str = "",
        max_tokens: int | None = None,
    ) -> list[dict[str, str]]:
        """Build an LLM-compatible message list within a token budget."""
        budget = max_tokens or self.max_tokens
        selected: list[ConversationTurn] = []
        used_tokens = self._estimate_tokens(system_prompt) if system_prompt else 0

        for turn in reversed(self.get_history(session_id)):
            turn_tokens = turn.token_count or self._estimate_tokens(turn.content)
            if used_tokens + turn_tokens > budget:
                if not selected:
                    selected.append(turn)
                break
            selected.append(turn)
            used_tokens += turn_tokens

        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.extend(turn.to_message() for turn in reversed(selected))
        return messages

    def clear_session(self, session_id: str) -> None:
        """Remove all retained turns for the session."""
        self._sessions.pop(session_id, None)
        logger.debug("[ConversationMemory] cleared session={}", session_id)

    def summarize_and_compact(
        self,
        session_id: str,
        keep_last_turns: int = 4,
        max_summary_chars: int = 400,
    ) -> str:
        """Summarize older turns and retain only the summary plus recent context."""
        turns = self.get_history(session_id)
        if len(turns) <= keep_last_turns:
            return ""

        keep_last_turns = max(keep_last_turns, 0)
        older_turns = turns[:-keep_last_turns] if keep_last_turns else turns
        recent_turns = turns[-keep_last_turns:] if keep_last_turns else []
        result = self.summary_store.summarize_turns(
            [(turn.role, turn.content) for turn in older_turns],
            max_chars=max_summary_chars,
        )
        if not result.content:
            return ""

        summary_content = f"[conversation summary]\n{result.content}"
        summary_turn = ConversationTurn(
            role="system",
            content=summary_content,
            metadata={
                "summary": True,
                "source_messages": result.source_messages,
                "truncated": result.truncated,
            },
            token_count=self._estimate_tokens(summary_content),
        )
        self._sessions[session_id] = deque([summary_turn, *recent_turns], maxlen=self.max_turns)
        logger.debug(
            "[ConversationMemory] summarized session={} source_turns={} kept_recent={}",
            session_id,
            len(older_turns),
            len(recent_turns),
        )
        return result.content

    def _estimate_tokens(self, content: str) -> int:
        if not content:
            return 0
        return max(1, (len(content) + 3) // 4)

    def _get_or_create_session(self, session_id: str) -> deque[ConversationTurn]:
        session = self._sessions.get(session_id)
        if session is None:
            session = deque(maxlen=self.max_turns)
            self._sessions[session_id] = session
        return session


ConversationMemory = ConversationMemoryStore
conversation_memory = ConversationMemoryStore()
