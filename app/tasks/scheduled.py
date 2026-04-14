"""Celery beat scheduled tasks — auto-generate weekly reports."""

from __future__ import annotations

from celery.schedules import crontab

from app.tasks.celery_app import celery_app

# Schedule: every Monday at 9:00 AM
celery_app.conf.beat_schedule = {
    "auto-weekly-report": {
        "task": "generate_report",
        "schedule": crontab(hour=9, minute=0, day_of_week=1),  # Monday 9:00
        "args": [],  # Will need to iterate projects — placeholder
        "enabled": False,  # Enable when ready
    },
}