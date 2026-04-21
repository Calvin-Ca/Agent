"""Conversation memory — manage multi-turn dialogue history per session.

Stores and retrieves conversation turns for a user session, enabling
context-aware follow-up questions and multi-turn interactions.

Features:
- Fixed-window history (keep last N turns)
- Token-aware truncation (stay within LLM context limits)
- Session isolation (by session_id / user_id)
- Automatic summarization of older turns (via summary.py)

Storage:
- Redis for active sessions (fast read/write, TTL-based expiry)
- MySQL for persistent history (audit trail)

Usage:
    from app.memory.conversation import conversation_memory

    # Add a turn
    conversation_memory.add_turn(
        session_id="sess-123",
        role="user",
        content="本周项目进度如何？",
    )

    # Get recent history
    history = conversation_memory.get_history(session_id="sess-123", max_turns=10)

    # Build messages list for LLM
    messages = conversation_memory.build_messages(
        session_id="sess-123",
        system_prompt="You are a helpful assistant.",
        max_tokens=4000,
    )

TODO: Implement with Redis + MySQL backends.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

from loguru import logger


@dataclass
class ConversationTurn:
    """A single turn in a conversation."""

    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)
    token_count: int = 0  # Estimated token count for this turn


class ConversationMemory:
    """Manages multi-turn conversation history with windowed retrieval.

    Args:
        max_turns: Maximum number of turns to retain per session (default: 20).
        max_tokens: Maximum total tokens across all retained turns (default: 8000).
        ttl_seconds: Time-to-live for session data in cache (default: 1 hour).

    TODO: Wire up to Redis (app.db.redis) and MySQL (app.crud) backends.
    """

    def __init__(
        self,
        max_turns: int = 20,
        max_tokens: int = 8000,
        ttl_seconds: int = 3600,
    ):
        self.max_turns = max_turns
        self.max_tokens = max_tokens
        self.ttl_seconds = ttl_seconds
        # In-memory fallback (replaced by Redis in production)
        self._sessions: dict[str, list[ConversationTurn]] = {}

    def add_turn(
        self,
        session_id: str,
        role: Literal["user", "assistant", "system"],
        content: str,
        **metadata,
    ) -> None:
        """Add a conversation turn to the session history.

        TODO: Persist to Redis + async write to MySQL.
        """
        turn = ConversationTurn(role=role, content=content, metadata=metadata)
        if session_id not in self._sessions:
            self._sessions[session_id] = []
        self._sessions[session_id].append(turn)

        # Trim to max_turns
        if len(self._sessions[session_id]) > self.max_turns:
            self._sessions[session_id] = self._sessions[session_id][-self.max_turns:]

        logger.debug("[ConversationMemory] add_turn session={} role={} chars={}", session_id, role, len(content))

    def get_history(self, session_id: str, max_turns: int | None = None) -> list[ConversationTurn]:
        """Retrieve recent conversation turns for a session.

        Args:
            session_id: The session identifier.
            max_turns: Override for maximum turns to return.

        Returns:
            List of ConversationTurn, ordered oldest first.
        """
        turns = self._sessions.get(session_id, [])
        limit = max_turns or self.max_turns
        return turns[-limit:]

    def build_messages(
        self,
        session_id: str,
        system_prompt: str = "",
        max_tokens: int | None = None,
    ) -> list[dict[str, str]]:
        """Build an OpenAI-compatible messages list from conversation history.

        Includes system prompt + recent turns, respecting token limits.

        Args:
            session_id: The session identifier.
            system_prompt: Optional system message to prepend.
            max_tokens: Maximum total tokens (uses self.max_tokens if not specified).

        Returns:
            List of {"role": str, "content": str} dicts.

        TODO: Implement token-aware truncation.
        """
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})

        for turn in self.get_history(session_id):
            messages.append({"role": turn.role, "content": turn.content})

        return messages

    def clear_session(self, session_id: str) -> None:
        """Clear all turns for a session.

        TODO: Also clear from Redis.
        """
        self._sessions.pop(session_id, None)
        logger.debug("[ConversationMemory] cleared session={}", session_id)

    def summarize_and_compact(self, session_id: str) -> str:
        """Summarize older turns and replace them with a summary turn.

        Uses LLM to compress conversation history, keeping recent turns intact.

        Returns:
            The generated summary text.

        TODO: Implement with LLM-based summarization (app.memory.summary).
        """
        logger.debug("[ConversationMemory] summarize session={}", session_id)
        return ""


# Singleton
conversation_memory = ConversationMemory()
