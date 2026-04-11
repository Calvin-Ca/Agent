"""Celery application instance.

Usage:
    celery -A app.tasks.celery_app worker --loglevel=info
    celery -A app.tasks.celery_app beat --loglevel=info
"""

from celery import Celery

from app.config import get_settings

settings = get_settings()

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

# Explicitly include task modules (autodiscover only finds tasks.py, not document_tasks.py)
celery_app.conf.update(
    include=["app.tasks.document_tasks"],
)