"""Report service — orchestrate agent workflow and persist results."""

from __future__ import annotations

import asyncio
from datetime import date, timedelta

from loguru import logger
from sqlalchemy import update

from app.config import get_settings
from app.db.mysql import get_session_factory
from app.models.report import Report


def generate_report_sync(project_id: str, user_id: str, week_start: str = "") -> dict:
    """Generate a weekly report (sync wrapper for Celery / CLI).

    Returns:
        {"success": bool, "report_id": str, "title": str, "content": str, "error": str | None}
    """
    from app.agents.graph import run_report_agent

    result = run_report_agent(project_id=project_id, user_id=user_id, week_start=week_start)

    if not result["success"]:
        return {"success": False, "report_id": "", "title": "", "content": "", "error": result["error"]}

    # Determine week dates
    if week_start:
        ws = date.fromisoformat(week_start)
    else:
        today = date.today()
        ws = today - timedelta(days=today.weekday())
    we = ws + timedelta(days=6)

    # Save to DB
    report_id = _save_report(
        project_id=project_id,
        creator_id=user_id,
        title=result["title"],
        week_start=ws,
        week_end=we,
        content=result["content"],
        summary=result["summary"],
    )

    return {
        "success": True,
        "report_id": report_id,
        "title": result["title"],
        "content": result["content"],
        "error": None,
    }


def _save_report(
    project_id: str, creator_id: str, title: str,
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