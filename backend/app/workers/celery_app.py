"""
Celery application factory.

`task_always_eager` lets the exact same task code run synchronously in-process
when CELERY_TASK_ALWAYS_EAGER=true (used for local development/testing without
a running Redis broker) while production always dispatches through Redis to a
real `celery -A app.workers.celery_app worker` process.
"""
from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "repurpose_ai",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.analysis_tasks",
        "app.workers.ingestion_tasks",
        "app.workers.prediction_tasks",
        "app.workers.cleanup_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    worker_hijack_root_logger=False,
    task_always_eager=getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False),
    task_eager_propagates=True,
)

celery_app.conf.beat_schedule = {
    "cleanup-stale-jobs-hourly": {
        "task": "app.workers.cleanup_tasks.cleanup_stale_jobs",
        "schedule": 3600.0,
    },
}
