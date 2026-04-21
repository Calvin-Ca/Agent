"""Episodic memory — records and retrieves past task execution episodes.

Stores the outcome of each workflow execution (what worked, what failed,
what strategies were used) so the agent can learn from experience:

- Avoid repeating failed strategies
- Reuse successful prompts / approaches
- Provide context for similar future tasks

Storage: MySQL for structured records, Milvus for semantic retrieval.

Usage:
    from app.memory.episodic import episodic_memory

    # Record an episode after workflow completes
    episodic_memory.record(
        project_id="proj-001",
        task_type="report",
        outcome="success",
        strategy="Used 4-week progress data + vector search top_k=8",
        quality_score=8.5,
        context={"week_start": "2026-04-14", "tokens_used": 3500},
    )

    # Retrieve similar past episodes for context
    episodes = episodic_memory.recall(
        project_id="proj-001",
        task_type="report",
        query="generate weekly report with limited data",
        limit=3,
    )

TODO: Implement with MySQL + Milvus backends.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from loguru import logger


@dataclass
class Episode:
    """A single task execution episode.

    Attributes:
        episode_id: Unique identifier.
        project_id: The project this episode belongs to.
        task_type: Type of task (report, query, etc.).
        outcome: Execution result (success, partial, failure).
        strategy: Description of the approach / strategy used.
        quality_score: Quality rating (0-10) from reviewer or user feedback.
        duration_seconds: How long the execution took.
        error_message: Error details if outcome is failure.
        context: Additional context (parameters, settings, etc.).
        timestamp: When this episode occurred.
    """

    episode_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    project_id: str = ""
    task_type: str = ""
    outcome: Literal["success", "partial", "failure"] = "success"
    strategy: str = ""
    quality_score: float = 0.0
    duration_seconds: float = 0.0
    error_message: str = ""
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "episode_id": self.episode_id,
            "project_id": self.project_id,
            "task_type": self.task_type,
            "outcome": self.outcome,
            "strategy": self.strategy,
            "quality_score": self.quality_score,
            "duration_seconds": round(self.duration_seconds, 2),
            "error_message": self.error_message,
            "context": self.context,
            "timestamp": self.timestamp,
        }


class EpisodicMemory:
    """Manages task execution history for experience-based learning.

    TODO: Wire up to MySQL (structured storage) and Milvus (semantic search).
    """

    def __init__(self):
        # In-memory fallback (replaced by DB in production)
        self._episodes: list[Episode] = []

    def record(
        self,
        project_id: str,
        task_type: str,
        outcome: Literal["success", "partial", "failure"],
        strategy: str = "",
        quality_score: float = 0.0,
        duration_seconds: float = 0.0,
        error_message: str = "",
        **context,
    ) -> str:
        """Record a completed workflow episode.

        Returns:
            The episode_id of the recorded episode.

        TODO: Persist to MySQL + embed strategy text to Milvus.
        """
        episode = Episode(
            project_id=project_id,
            task_type=task_type,
            outcome=outcome,
            strategy=strategy,
            quality_score=quality_score,
            duration_seconds=duration_seconds,
            error_message=error_message,
            context=context,
        )
        self._episodes.append(episode)
        logger.debug(
            "[EpisodicMemory] recorded episode={} project={} task={} outcome={}",
            episode.episode_id, project_id, task_type, outcome,
        )
        return episode.episode_id

    def recall(
        self,
        project_id: str = "",
        task_type: str = "",
        query: str = "",
        outcome: str = "",
        limit: int = 5,
    ) -> list[Episode]:
        """Retrieve relevant past episodes.

        Args:
            project_id: Filter by project (optional).
            task_type: Filter by task type (optional).
            query: Semantic search query (optional, requires Milvus).
            outcome: Filter by outcome (optional).
            limit: Maximum episodes to return.

        Returns:
            List of matching Episode records, most recent first.

        TODO: Implement Milvus semantic search when query is provided.
        """
        results = self._episodes

        if project_id:
            results = [e for e in results if e.project_id == project_id]
        if task_type:
            results = [e for e in results if e.task_type == task_type]
        if outcome:
            results = [e for e in results if e.outcome == outcome]

        # Most recent first
        results = sorted(results, key=lambda e: e.timestamp, reverse=True)
        return results[:limit]

    def get_success_rate(self, project_id: str = "", task_type: str = "") -> float:
        """Calculate success rate for a given project/task type.

        Returns:
            Success rate as a float between 0.0 and 1.0.
        """
        episodes = self.recall(project_id=project_id, task_type=task_type, limit=100)
        if not episodes:
            return 0.0
        successes = sum(1 for e in episodes if e.outcome == "success")
        return successes / len(episodes)

    def get_average_quality(self, project_id: str = "", task_type: str = "") -> float:
        """Calculate average quality score for rated episodes.

        Returns:
            Average quality score, or 0.0 if no rated episodes exist.
        """
        episodes = self.recall(project_id=project_id, task_type=task_type, limit=100)
        rated = [e for e in episodes if e.quality_score > 0]
        if not rated:
            return 0.0
        return sum(e.quality_score for e in rated) / len(rated)


# Singleton
episodic_memory = EpisodicMemory()
