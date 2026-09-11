"""Periodic maintenance tasks (wired to Celery beat in celery_app.py)."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.core.constants import ACTIVE_EXPERIMENT_STATUSES, JobStatus
from app.models.job import Job
from app.workers.celery_app import celery_app
from app.workers.task_utils import task_db

STALE_JOB_THRESHOLD_HOURS = 6


@celery_app.task(name="app.workers.cleanup_tasks.cleanup_stale_jobs")
def cleanup_stale_jobs() -> dict:
    """Marks jobs stuck in RUNNING/QUEUED for too long as FAILED so they stop blocking dashboards."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=STALE_JOB_THRESHOLD_HOURS)
    updated = 0
    with task_db() as db:
        stale_jobs = db.scalars(
            select(Job).where(
                Job.status.in_([JobStatus.QUEUED.value, JobStatus.RUNNING.value]),
                Job.created_at < cutoff,
            )
        ).all()
        for job in stale_jobs:
            job.status = JobStatus.FAILED.value
            job.error = f"Job timed out after {STALE_JOB_THRESHOLD_HOURS}h and was automatically marked failed."
            job.completed_at = datetime.now(timezone.utc)
            updated += 1
    return {"stale_jobs_marked_failed": updated}


@celery_app.task(name="app.workers.cleanup_tasks.cleanup_expired_refresh_tokens")
def cleanup_expired_refresh_tokens() -> dict:
    from app.models.refresh_token import RefreshToken

    deleted = 0
    with task_db() as db:
        expired = db.scalars(select(RefreshToken).where(RefreshToken.expires_at < datetime.now(timezone.utc))).all()
        for token in expired:
            db.delete(token)
            deleted += 1
    return {"expired_refresh_tokens_deleted": deleted}
