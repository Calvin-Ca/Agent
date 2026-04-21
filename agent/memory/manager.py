"""Unified memory manager spanning structured, vector, cache, and agent memory."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

from loguru import logger
from sqlalchemy import text

from agent.memory.conversation import ConversationMemoryStore, conversation_memory
from agent.memory.episodic import EpisodicMemoryStore, episodic_memory
from agent.memory.knowledge_graph import KnowledgeGraphStore
from agent.memory.long_term import LongTermMemoryStore, vector_memory
from agent.memory.retriever import HybridRetriever
from agent.memory.summary import ConversationSummaryStore, summary_memory
from agent.memory.working import WorkingMemory
from app.db.mysql import get_session_factory
from app.db.redis import cache_delete, cache_delete_pattern, cache_get, cache_set, distributed_lock
from app.models.report import Report


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


class StructuredMemoryStore:
    """MySQL-backed structured memory for projects, progress, and reports."""

    def get_project_info(self, project_id: str) -> dict:
        async def _query():
            factory = get_session_factory()
            async with factory() as session:
                result = await session.execute(
                    text(
                        "SELECT id, name, code, description, status, created_at "
                        "FROM projects WHERE id = :id AND is_deleted = 0"
                    ),
                    {"id": project_id},
                )
                row = result.first()
                if row is None:
                    return {}
                return {
                    "id": row[0],
                    "name": row[1],
                    "code": row[2],
                    "description": row[3],
                    "status": row[4],
                    "created_at": str(row[5]),
                }

        return _run(_query())

    def get_recent_progress(self, project_id: str, weeks: int = 4) -> list[dict]:
        async def _query():
            factory = get_session_factory()
            since = date.today() - timedelta(weeks=weeks)
            async with factory() as session:
                result = await session.execute(
                    text(
                        "SELECT record_date, overall_progress, milestone, description, blockers, next_steps "
                        "FROM progress_records "
                        "WHERE project_id = :pid AND record_date >= :since AND is_deleted = 0 "
                        "ORDER BY record_date DESC"
                    ),
                    {"pid": project_id, "since": since},
                )
                rows = result.fetchall()
                return [
                    {
                        "date": str(row[0]),
                        "progress": row[1],
                        "milestone": row[2],
                        "description": row[3],
                        "blockers": row[4],
                        "next_steps": row[5],
                    }
                    for row in rows
                ]

        return _run(_query())

    def get_recent_reports(self, project_id: str, limit: int = 3) -> list[dict]:
        async def _query():
            factory = get_session_factory()
            async with factory() as session:
                result = await session.execute(
                    text(
                        "SELECT title, week_start, week_end, summary, status "
                        "FROM reports "
                        "WHERE project_id = :pid AND is_deleted = 0 "
                        "ORDER BY week_start DESC LIMIT :lim"
                    ),
                    {"pid": project_id, "lim": limit},
                )
                rows = result.fetchall()
                return [
                    {
                        "title": row[0],
                        "week_start": str(row[1]),
                        "week_end": str(row[2]),
                        "summary": row[3],
                        "status": row[4],
                    }
                    for row in rows
                ]

        return _run(_query())

    def get_document_list(self, project_id: str) -> list[dict]:
        async def _query():
            factory = get_session_factory()
            async with factory() as session:
                result = await session.execute(
                    text(
                        "SELECT id, filename, file_type, process_status, chunk_count, created_at "
                        "FROM documents "
                        "WHERE project_id = :pid AND is_deleted = 0 "
                        "ORDER BY created_at DESC"
                    ),
                    {"pid": project_id},
                )
                rows = result.fetchall()
                return [
                    {
                        "id": row[0],
                        "filename": row[1],
                        "file_type": row[2],
                        "status": row[3],
                        "chunks": row[4],
                        "created_at": str(row[5]),
                    }
                    for row in rows
                ]

        return _run(_query())

    def save_report(
        self,
        *,
        project_id: str,
        creator_id: str,
        title: str,
        week_start: date,
        week_end: date,
        content: str,
        summary: str,
    ) -> str:
        async def _insert():
            factory = get_session_factory()
            async with factory() as session:
                report = Report(
                    project_id=project_id,
                    creator_id=creator_id,
                    title=title,
                    week_start=week_start,
                    week_end=week_end,
                    content=content,
                    summary=summary,
                    status=2,
                )
                session.add(report)
                await session.flush()
                await session.refresh(report)
                await session.commit()
                return report.id

        loop = asyncio.new_event_loop()
        try:
            report_id = loop.run_until_complete(_insert())
            logger.info("Report saved {}", report_id)
            return report_id
        finally:
            loop.close()


class CacheMemoryStore:
    """Redis-backed short-term cache and distributed locks."""

    async def get(self, key: str):
        return await cache_get(key)

    async def set(self, key: str, value, ttl: int = 300) -> None:
        await cache_set(key, value, ttl=ttl)

    async def delete(self, key: str) -> None:
        await cache_delete(key)

    async def delete_pattern(self, pattern: str) -> int:
        return await cache_delete_pattern(pattern)

    def lock(self, name: str, timeout: int = 60, blocking_timeout: int = 5):
        return distributed_lock(name, timeout=timeout, blocking_timeout=blocking_timeout)


class MemoryManager:
    """Coordinate working, conversation, episodic, vector, structured, and cache memory."""

    def __init__(
        self,
        working: WorkingMemory | None = None,
        long_term: LongTermMemoryStore | None = None,
        knowledge_graph: KnowledgeGraphStore | None = None,
        structured: StructuredMemoryStore | None = None,
        short_term: CacheMemoryStore | None = None,
        conversation: ConversationMemoryStore | None = None,
        episodic: EpisodicMemoryStore | None = None,
        summary: ConversationSummaryStore | None = None,
    ) -> None:
        self.working = working or WorkingMemory()
        self.long_term = long_term or vector_memory
        self.knowledge_graph = knowledge_graph or KnowledgeGraphStore()
        self.structured = structured or StructuredMemoryStore()
        self.short_term = short_term or CacheMemoryStore()
        self.summary = summary or summary_memory
        self.conversation = conversation or (
            conversation_memory if self.summary is summary_memory else ConversationMemoryStore(summary_store=self.summary)
        )
        self.episodic = episodic or episodic_memory
        self.retriever = HybridRetriever(self.working, self.long_term)

    def remember_turn(self, user_text: str, assistant_text: str, session_id: str = "", **metadata) -> None:
        self.working.append("user", user_text)
        self.working.append("assistant", assistant_text)
        if session_id:
            self.conversation.add_turn(session_id, "user", user_text, **metadata)
            self.conversation.add_turn(session_id, "assistant", assistant_text, **metadata)


structured_memory = StructuredMemoryStore()
cache_memory = CacheMemoryStore()
memory_manager = MemoryManager(
    structured=structured_memory,
    long_term=vector_memory,
    short_term=cache_memory,
    conversation=conversation_memory,
    episodic=episodic_memory,
    summary=summary_memory,
)
