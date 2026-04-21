"""Celery task for async report generation."""

from __future__ import annotations

import time

from loguru import logger

from app.tasks.celery_app import celery_app
from app.db.redis import distributed_lock
from agent.infra.logger import request_log_scope


@celery_app.task(
    name="generate_report",
    bind=True,
    max_retries=1,
    default_retry_delay=30,
)
def generate_report_task(
    self,
    project_id: str,
    user_id: str,
    week_start: str = "",
    request_id: str = "-",
    request_log_file: str = "",
) -> dict:
    """Generate a weekly report asynchronously.

    Uses a distributed lock to prevent duplicate generation
    for the same project in the same week.
    """
    import asyncio

    with request_log_scope(
        request_id=request_id,
        user_id=str(user_id),
        request_log_file=request_log_file,
    ):
        task_start = time.perf_counter()
        logger.info(
            "Report task started | task_id={} project={} week_start='{}'",
            self.request.id,
            project_id,
            week_start or "-",
        )

        lock_key = f"report:{project_id}:{week_start or 'current'}"

        async def _run():
            async with distributed_lock(lock_key, timeout=300) as acquired:
                if not acquired:
                    return {"success": False, "error": "另一个报告生成任务正在进行中"}

                from agent.core.react_engine import report_workflow
                return report_workflow.run_and_save(project_id, user_id, week_start)

        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(_run())
        finally:
            loop.close()

        elapsed_ms = (time.perf_counter() - task_start) * 1000
        if result["success"]:
            logger.info(
                "Report task done | report_id={} | elapsed={:.0f}ms",
                result.get("report_id"),
                elapsed_ms,
            )
        else:
            logger.error(
                "Report task failed | error={} | elapsed={:.0f}ms",
                result.get("error"),
                elapsed_ms,
            )

        return result
