"""Minimal in-memory entity-relation store."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Triple:
    subject: str
    relation: str
    object: str


class KnowledgeGraphStore:
    """Store and query entity triples."""

    def __init__(self) -> None:
        self._triples: set[Triple] = set()

    def add(self, subject: str, relation: str, object_: str) -> None:
        self._triples.add(Triple(subject=subject, relation=relation, object=object_))

    def query(self, subject: str | None = None, relation: str | None = None) -> list[Triple]:
        return [
            triple
            for triple in self._triples
            if (subject is None or triple.subject == subject)
            and (relation is None or triple.relation == relation)
        ]

