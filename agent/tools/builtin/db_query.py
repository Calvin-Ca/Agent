"""Built-in structured-data query tools."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

from loguru import logger
from sqlalchemy import text

from agent.memory.long_term import vector_memory
from agent.tools.base import BaseTool, ToolOutput
from app.db.mysql import get_session_factory


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


def _query_project_info(project_id: str) -> dict:
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

    info = _run(_query())
    logger.debug("Project info fetched for {}", project_id)
    return info


def _query_recent_progress(project_id: str, weeks: int = 4) -> list[dict]:
    async def _query():
        factory = get_session_factory()
        since = date.today() - timedelta(weeks=weeks)
        async with factory() as session:
            result = await session.execute(
                text(
                    "SELECT record_date, overall_progress, milestone, "
                    "description, blockers, next_steps "
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


def _query_document_list(project_id: str) -> list[dict]:
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


def _query_recent_reports(project_id: str, limit: int = 3) -> list[dict]:
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


class GetProjectInfoTool(BaseTool):
    name = "db.get_project_info"
    description = "Fetch project metadata from the relational database"

    def execute(self, *, project_id: str, **kwargs) -> ToolOutput:
        try:
            info = _query_project_info(project_id)
            if not info:
                return ToolOutput(success=False, error=f"项目不存在: {project_id}")
            return ToolOutput(success=True, data=info)
        except Exception as exc:
            return ToolOutput(success=False, error=str(exc))


class GetRecentProgressTool(BaseTool):
    name = "db.get_recent_progress"
    description = "Fetch recent progress records for a project"

    def execute(self, *, project_id: str, weeks: int = 4, **kwargs) -> ToolOutput:
        try:
            return ToolOutput(success=True, data=_query_recent_progress(project_id, weeks=weeks))
        except Exception as exc:
            return ToolOutput(success=False, error=str(exc))


class GetRecentReportsTool(BaseTool):
    name = "db.get_recent_reports"
    description = "Fetch recent reports for a project"

    def execute(self, *, project_id: str, limit: int = 3, **kwargs) -> ToolOutput:
        try:
            return ToolOutput(success=True, data=_query_recent_reports(project_id, limit=limit))
        except Exception as exc:
            return ToolOutput(success=False, error=str(exc))


class GetDocumentListTool(BaseTool):
    name = "db.get_document_list"
    description = "Fetch uploaded document metadata for a project"

    def execute(self, *, project_id: str, **kwargs) -> ToolOutput:
        try:
            return ToolOutput(success=True, data=_query_document_list(project_id))
        except Exception as exc:
            return ToolOutput(success=False, error=str(exc))


class VectorSearchTool(BaseTool):
    name = "vector.search_documents"
    description = "Search for relevant document chunks using semantic similarity"

    def execute(
        self,
        *,
        query: str,
        project_id: str,
        top_k: int = 8,
        score_threshold: float = 0.4,
        **kwargs,
    ) -> ToolOutput:
        try:
            chunks = vector_memory.search(
                query=query,
                project_id=project_id,
                top_k=top_k,
                score_threshold=score_threshold,
            )
            return ToolOutput(success=True, data=chunks, metadata={"count": len(chunks)})
        except Exception as exc:
            return ToolOutput(success=False, data=[], error=str(exc))


class MultiQuerySearchTool(BaseTool):
    name = "vector.search_multi"
    description = "Search multiple semantic queries and deduplicate the results"

    def execute(
        self,
        *,
        queries: list[str],
        project_id: str,
        top_k_per_query: int = 5,
        score_threshold: float = 0.4,
        **kwargs,
    ) -> ToolOutput:
        try:
            all_chunks: list[str] = []
            seen: set[str] = set()
            for query in queries:
                chunks = vector_memory.search(
                    query=query,
                    project_id=project_id,
                    top_k=top_k_per_query,
                    score_threshold=score_threshold,
                )
                for chunk in chunks:
                    key = chunk[:100]
                    if key not in seen:
                        seen.add(key)
                        all_chunks.append(chunk)
            return ToolOutput(success=True, data=all_chunks, metadata={"count": len(all_chunks)})
        except Exception as exc:
            return ToolOutput(success=False, data=[], error=str(exc))
