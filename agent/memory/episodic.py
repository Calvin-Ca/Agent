"""Episodic memory for recording and recalling execution experience."""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Literal

from loguru import logger


@dataclass(slots=True)
class Episode:
    """A single task execution episode."""

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

    def to_dict(self) -> dict[str, Any]:
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


class EpisodicMemoryStore:
    """In-memory episodic memory with lightweight text matching for recall."""

    def __init__(self) -> None:
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
        """Record a finished execution episode and return its ID."""
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
            episode.episode_id,
            project_id,
            task_type,
            outcome,
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
        """Recall the most relevant episodes, newest first."""
        results = self._episodes

        if project_id:
            results = [episode for episode in results if episode.project_id == project_id]
        if task_type:
            results = [episode for episode in results if episode.task_type == task_type]
        if outcome:
            results = [episode for episode in results if episode.outcome == outcome]

        if query.strip():
            scored = [
                (self._score_episode(episode, query), episode)
                for episode in results
            ]
            matching = [item for item in scored if item[0] > 0]
            if matching:
                matching.sort(
                    key=lambda item: (
                        item[0],
                        self._outcome_rank(item[1].outcome),
                        item[1].quality_score,
                        item[1].timestamp,
                    ),
                    reverse=True,
                )
                return [episode for _, episode in matching[:limit]]

        results = sorted(results, key=lambda episode: episode.timestamp, reverse=True)
        return results[:limit]

    def get_success_rate(self, project_id: str = "", task_type: str = "") -> float:
        """Return success ratio within the filtered episode slice."""
        episodes = self.recall(project_id=project_id, task_type=task_type, limit=100)
        if not episodes:
            return 0.0
        successes = sum(1 for episode in episodes if episode.outcome == "success")
        return successes / len(episodes)

    def get_average_quality(self, project_id: str = "", task_type: str = "") -> float:
        """Return average quality score for rated episodes."""
        episodes = self.recall(project_id=project_id, task_type=task_type, limit=100)
        rated = [episode for episode in episodes if episode.quality_score > 0]
        if not rated:
            return 0.0
        return sum(episode.quality_score for episode in rated) / len(rated)

    def _score_episode(self, episode: Episode, query: str) -> int:
        haystack = " ".join(
            str(part)
            for part in (
                episode.project_id,
                episode.task_type,
                episode.outcome,
                episode.strategy,
                episode.error_message,
                episode.context,
            )
        ).lower()
        terms = [term for term in query.lower().split() if term]
        return sum(1 for term in terms if term in haystack)

    def _outcome_rank(self, outcome: str) -> int:
        ranks = {"success": 2, "partial": 1, "failure": 0}
        return ranks.get(outcome, -1)


EpisodicMemory = EpisodicMemoryStore
episodic_memory = EpisodicMemoryStore()
