"""Semantic and hybrid retrieval helpers."""

from __future__ import annotations

from agent.memory.long_term import LongTermMemoryStore
from agent.memory.working import WorkingMemory


class HybridRetriever:
    """Combine recent-turn memory with long-term semantic recall."""

    def __init__(
        self,
        working_memory: WorkingMemory | None = None,
        long_term_memory: LongTermMemoryStore | None = None,
    ) -> None:
        self.working_memory = working_memory or WorkingMemory()
        self.long_term_memory = long_term_memory or LongTermMemoryStore()

    def retrieve(self, query: str, project_id: str, top_k: int = 8) -> list[str]:
        snippets = [item.content for item in self.working_memory.items() if query[:8] in item.content]
        snippets.extend(self.long_term_memory.search(query=query, project_id=project_id, top_k=top_k))
        seen: set[str] = set()
        deduped: list[str] = []
        for snippet in snippets:
            if snippet not in seen:
                seen.add(snippet)
                deduped.append(snippet)
        return deduped
