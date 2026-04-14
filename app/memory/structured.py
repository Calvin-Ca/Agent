"""Structured memory — MySQL-backed store for projects, progress, reports.

Delegates to app.crud/ for ORM operations and raw SQL for agent queries.
Implements StructuredStore protocol.
"""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

from loguru import logger
from sqlalchemy import text

from app.db.mysql import get_session_factory
from app.models.report import Report


def _run(coro):
    """Run async in sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


class StructuredMemory:
    """MySQL-backed structured data store."""

    def get_project_info(self, project_id: str) -> dict:
        """Fetch project metadata."""

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
                    "id": row[0], "name": row[1], "code": row[2],
                    "description": row[3], "status": row[4],
                    "created_at": str(row[5]),
                }

        info = _run(_query())
        logger.debug("Project info: {}", info.get("name", "not found"))
        return info

    def get_recent_progress(self, project_id: str, weeks: int = 4) -> list[dict]:
        """Fetch recent progress records for a project."""

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
                        "date": str(r[0]), "progress": r[1], "milestone": r[2],
                        "description": r[3], "blockers": r[4], "next_steps": r[5],
                    }
                    for r in rows
                ]

        records = _run(_query())
        logger.debug("Progress records: {} found for project {}", len(records), project_id)
        return records

    def get_recent_reports(self, project_id: str, limit: int = 3) -> list[dict]:
        """Fetch recent report summaries for context."""

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
                        "title": r[0], "week_start": str(r[1]),
                        "week_end": str(r[2]), "summary": r[3], "status": r[4],
                    }
                    for r in rows
                ]

        reports = _run(_query())
        logger.debug("Recent reports: {} found", len(reports))
        return reports

    def get_document_list(self, project_id: str) -> list[dict]:
        """Fetch uploaded document metadata for a project."""

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
                        "id": r[0], "filename": r[1], "file_type": r[2],
                        "status": r[3], "chunks": r[4], "created_at": str(r[5]),
                    }
                    for r in rows
                ]

        docs = _run(_query())
        logger.debug("Documents: {} found for project {}", len(docs), project_id)
        return docs

    def save_report(
        self, *, project_id: str, creator_id: str, title: str,
        week_start: date, week_end: date, content: str, summary: str,
    ) -> str:
        """Save report to MySQL. Returns report ID."""

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
                    status=2,  # final
                )
                session.add(report)
                await session.flush()
                await session.refresh(report)
                await session.commit()
                return report.id

        loop = asyncio.new_event_loop()
        try:
            report_id = loop.run_until_complete(_insert())
            logger.info("Report saved: {}", report_id)
            return report_id
        finally:
            loop.close()


# Singleton
structured_memory = StructuredMemory()
