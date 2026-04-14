"""Celery task for async report generation."""

from __future__ import annotations

from loguru import logger

from app.tasks.celery_app import celery_app
from app.db.redis import distributed_lock


@celery_app.task(
    name="generate_report",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
)
def generate_report_task(self, project_id: str, user_id: str, week_start: str = "") -> dict:
    """Generate a weekly report asynchronously.

    Uses a distributed lock to prevent duplicate generation
    for the same project in the same week.
    """
    import asyncio

    lock_key = f"report:{project_id}:{week_start or 'current'}"

    async def _run():
        async with distributed_lock(lock_key, timeout=300) as acquired:
            if not acquired:
                return {"success": False, "error": "另一个报告生成任务正在进行中"}

            from app.services.report_service import generate_report_sync
            return generate_report_sync(project_id, user_id, week_start)

    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(_run())
    finally:
        loop.close()

    if result["success"]:
        logger.info("Report task done: {}", result.get("report_id"))
    else:
        logger.error("Report task failed: {}", result.get("error"))

    return result