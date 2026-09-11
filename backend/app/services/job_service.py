"""Tracks Job rows (the DB-persisted mirror of Celery task state) and emits WebSocket progress events."""
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.core.constants import JobStatus, JobType, TERMINAL_JOB_STATUSES
from app.core.exceptions import NotFoundError
from app.models.job import Job


def create_job(
    db: Session,
    job_type: JobType | str,
    user_id: uuid.UUID | None = None,
    project_id: uuid.UUID | None = None,
    experiment_id: uuid.UUID | None = None,
    analysis_id: uuid.UUID | None = None,
    dataset_id: uuid.UUID | None = None,
    task_id: str | None = None,
) -> Job:
    job = Job(
        job_type=job_type.value if isinstance(job_type, JobType) else job_type,
        status=JobStatus.QUEUED.value,
        task_id=task_id,
        user_id=user_id,
        project_id=project_id,
        experiment_id=experiment_id,
        analysis_id=analysis_id,
        dataset_id=dataset_id,
    )
    db.add(job)
    db.flush()
    db.refresh(job)
    _emit(job, event="started" if job.status == JobStatus.RUNNING.value else "queued")
    return job


def get_job_or_404(db: Session, job_id: uuid.UUID) -> Job:
    job = db.get(Job, job_id)
    if not job:
        raise NotFoundError("Job was not found", code="JOB_NOT_FOUND")
    return job


def update_job(
    db: Session,
    job_id: uuid.UUID,
    status: JobStatus | str | None = None,
    progress: int | None = None,
    message: str | None = None,
    result: dict | None = None,
    error: str | None = None,
) -> Job:
    job = get_job_or_404(db, job_id)
    status_value = status.value if isinstance(status, JobStatus) else status

    if status_value == JobStatus.RUNNING.value and job.started_at is None:
        job.started_at = datetime.now(timezone.utc)
    if status_value in {s.value for s in TERMINAL_JOB_STATUSES}:
        job.completed_at = datetime.now(timezone.utc)

    if status_value is not None:
        job.status = status_value
    if progress is not None:
        job.progress = progress
    if message is not None:
        job.message = message
    if result is not None:
        job.result = result
    if error is not None:
        job.error = error

    db.flush()
    db.refresh(job)

    event = "progress"
    if job.status == JobStatus.COMPLETED.value:
        event = "completed"
    elif job.status == JobStatus.FAILED.value:
        event = "failed"
    elif job.status == JobStatus.CANCELLED.value:
        event = "failed"
    _emit(job, event=event)
    return job


def _emit(job: Job, event: str) -> None:
    from app.websocket.handlers import publish_ws_event

    payload = {
        "event": event,
        "job_id": str(job.id),
        "job_type": job.job_type,
        "status": job.status,
        "progress": job.progress,
        "message": job.message,
    }
    publish_ws_event(f"jobs:{job.id}", payload)
    if job.experiment_id:
        publish_ws_event(f"experiments:{job.experiment_id}", payload)
    if job.analysis_id:
        publish_ws_event(f"analyses:{job.analysis_id}", payload)
