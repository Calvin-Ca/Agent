"""Short-horizon working memory."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass


@dataclass(slots=True)
class WorkingMemoryItem:
    role: str
    content: str


class WorkingMemory:
    """Sliding window buffer with coarse summarization."""

    def __init__(self, max_items: int = 8) -> None:
        self._items: deque[WorkingMemoryItem] = deque(maxlen=max_items)

    def append(self, role: str, content: str) -> None:
        self._items.append(WorkingMemoryItem(role=role, content=content))

    def items(self) -> list[WorkingMemoryItem]:
        return list(self._items)

    def summary(self) -> str:
        return "\n".join(f"{item.role}: {item.content}" for item in self._items)

