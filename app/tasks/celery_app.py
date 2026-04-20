"""Celery application instance.

Usage:
    celery -A app.tasks.celery_app worker --loglevel=info
    celery -A app.tasks.celery_app beat --loglevel=info
"""

from celery import Celery
from celery.signals import beat_init, worker_init
from loguru import logger

from app.config import get_settings
from app.observability.logger import setup_logging

settings = get_settings()


def _init_celery_logging() -> None:
    """Initialize shared logging for Celery worker/beat processes."""
    setup_logging(
        log_level="DEBUG" if settings.debug else "INFO",
        json_output=settings.app_env == "production",
    )

celery_app = Celery(
    "smart_weekly_report",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",

    # Timezone
    timezone="Asia/Shanghai",
    enable_utc=True,

    # Reliability
    task_acks_late=True,                  # ACK after task completes (not on receive)
    worker_prefetch_multiplier=1,         # Don't prefetch — one task at a time per worker
    task_reject_on_worker_lost=True,      # Re-queue if worker crashes

    # Limits
    task_soft_time_limit=300,             # 5 min soft limit
    task_time_limit=600,                  # 10 min hard limit
    worker_max_tasks_per_child=100,       # Restart worker after 100 tasks (memory leak protection)

    # Result
    result_expires=3600,                  # Results expire after 1 hour
)

@worker_init.connect
def init_worker(**kwargs):
    """Initialize unified logging and register built-in tools for Celery."""
    _init_celery_logging()
    logger.info("Celery worker logging initialized")

    from app.tools.registry import auto_discover_tools
    auto_discover_tools()


@beat_init.connect
def init_beat(**kwargs):
    """Initialize unified logging for Celery beat."""
    _init_celery_logging()
    logger.info("Celery beat logging initialized")


# Explicitly include task modules (autodiscover only finds tasks.py, not document_tasks.py)
celery_app.conf.update(
    include=[
        "app.tasks.document_tasks",
        "app.tasks.report_tasks",
        "app.tasks.scheduled",
    ],
)
