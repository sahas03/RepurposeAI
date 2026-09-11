import time
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import (
    ACTIVE_EXPERIMENT_STATUSES,
    ExperimentStatus,
    JobStatus,
    ProjectStatus,
)
from app.models.analysis import Analysis
from app.models.audit_log import AuditLog
from app.models.dataset import Dataset
from app.models.experiment import Experiment
from app.models.prediction import Prediction
from app.models.project import Project
from app.models.user import User

_process_start = time.monotonic()

HIGH_CONFIDENCE_THRESHOLD = 0.75


def dashboard_overview(db: Session, user: User) -> dict:
    is_admin = user.role.name == "admin"
    project_filter = () if is_admin else (Project.owner_id == user.id,)

    total_projects = db.scalar(select(func.count()).select_from(Project).where(*project_filter)) or 0
    active_projects = db.scalar(select(func.count()).select_from(Project).where(*project_filter, Project.status == ProjectStatus.ACTIVE.value)) or 0

    exp_stmt = select(func.count()).select_from(Experiment)
    if not is_admin:
        exp_stmt = exp_stmt.join(Project, Project.id == Experiment.project_id).where(Project.owner_id == user.id)
    total_experiments = db.scalar(exp_stmt) or 0

    def exp_count(status_val):
        stmt = select(func.count()).select_from(Experiment)
        if not is_admin:
            stmt = stmt.join(Project, Project.id == Experiment.project_id).where(Project.owner_id == user.id)
        return db.scalar(stmt.where(Experiment.status == status_val)) or 0

    running_experiments = sum(exp_count(s.value) for s in ACTIVE_EXPERIMENT_STATUSES)
    completed_experiments = exp_count(ExperimentStatus.COMPLETED.value)
    failed_experiments = exp_count(ExperimentStatus.FAILED.value)

    ds_stmt = select(func.count()).select_from(Dataset)
    if not is_admin:
        ds_stmt = ds_stmt.join(Project, Project.id == Dataset.project_id).where(Project.owner_id == user.id)
    total_datasets = db.scalar(ds_stmt) or 0

    an_stmt = select(func.count()).select_from(Analysis).where(Analysis.status.in_([JobStatus.RUNNING.value, JobStatus.QUEUED.value]))
    if not is_admin:
        an_stmt = an_stmt.join(Experiment, Experiment.id == Analysis.experiment_id).join(Project, Project.id == Experiment.project_id).where(Project.owner_id == user.id)
    analyses_running = db.scalar(an_stmt) or 0

    pred_stmt = select(func.count()).select_from(Prediction)
    if not is_admin:
        pred_stmt = pred_stmt.join(Project, Project.id == Prediction.project_id).where(Project.owner_id == user.id)
    predictions_generated = db.scalar(pred_stmt) or 0

    high_confidence_candidates = db.scalar(pred_stmt.where(Prediction.confidence >= HIGH_CONFIDENCE_THRESHOLD)) or 0

    return {
        "total_projects": total_projects,
        "active_projects": active_projects,
        "total_experiments": total_experiments,
        "running_experiments": running_experiments,
        "completed_experiments": completed_experiments,
        "failed_experiments": failed_experiments,
        "total_datasets": total_datasets,
        "analyses_running": analyses_running,
        "predictions_generated": predictions_generated,
        "high_confidence_candidates": high_confidence_candidates,
    }


def recent_activity(db: Session, user: User, limit: int = 20) -> list[dict]:
    stmt = select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit)
    if user.role.name != "admin":
        stmt = stmt.where(AuditLog.user_id == user.id)
    logs = db.scalars(stmt).all()
    return [
        {
            "type": log.action,
            "title": log.action.replace("_", " ").title(),
            "description": f"{log.resource_type or 'resource'} {log.resource_id or ''}".strip(),
            "timestamp": log.timestamp,
            "resource_id": log.resource_id,
        }
        for log in logs
    ]


def recent_experiments(db: Session, user: User, limit: int = 10) -> list[Experiment]:
    stmt = select(Experiment).order_by(Experiment.created_at.desc()).limit(limit)
    if user.role.name != "admin":
        stmt = stmt.join(Project, Project.id == Experiment.project_id).where(Project.owner_id == user.id)
    return list(db.scalars(stmt).all())


def recent_predictions(db: Session, user: User, limit: int = 10) -> list[Prediction]:
    stmt = select(Prediction).order_by(Prediction.created_at.desc()).limit(limit)
    if user.role.name != "admin":
        stmt = stmt.join(Project, Project.id == Prediction.project_id).where(Project.owner_id == user.id)
    return list(db.scalars(stmt).all())


def system_status(db: Session) -> dict:
    db_status = "healthy"
    try:
        db.execute(select(1))
    except Exception:
        db_status = "unhealthy"

    redis_status = "healthy"
    worker_count = 0
    try:
        import redis as redis_lib
        client = redis_lib.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=1)
        client.ping()
        try:
            from app.workers.celery_app import celery_app
            inspected = celery_app.control.inspect(timeout=1).ping() or {}
            worker_count = len(inspected)
        except Exception:
            worker_count = 0
    except Exception:
        redis_status = "unhealthy"

    return {
        "database": db_status,
        "redis": redis_status,
        "celery_workers": worker_count,
        "environment": settings.ENVIRONMENT,
        "version": settings.APP_VERSION,
        "uptime_seconds": round(time.monotonic() - _process_start, 2),
    }


def dashboard_metrics(db: Session, user: User) -> dict:
    is_admin = user.role.name == "admin"

    pred_stmt = select(Prediction)
    if not is_admin:
        pred_stmt = pred_stmt.join(Project, Project.id == Prediction.project_id).where(Project.owner_id == user.id)
    predictions = db.scalars(pred_stmt).all()
    predictions_by_confidence = {"low": 0, "medium": 0, "high": 0}
    for p in predictions:
        if p.confidence >= 0.75:
            predictions_by_confidence["high"] += 1
        elif p.confidence >= 0.5:
            predictions_by_confidence["medium"] += 1
        else:
            predictions_by_confidence["low"] += 1

    exp_stmt = select(Experiment.status, func.count(Experiment.id)).group_by(Experiment.status)
    if not is_admin:
        exp_stmt = exp_stmt.join(Project, Project.id == Experiment.project_id).where(Project.owner_id == user.id)
    experiments_by_status = {row[0]: row[1] for row in db.execute(exp_stmt).all()}

    ds_stmt = select(Dataset.status, func.count(Dataset.id)).group_by(Dataset.status)
    if not is_admin:
        ds_stmt = ds_stmt.join(Project, Project.id == Dataset.project_id).where(Project.owner_id == user.id)
    datasets_by_status = {row[0]: row[1] for row in db.execute(ds_stmt).all()}

    an_stmt = select(Analysis.analysis_type, func.count(Analysis.id)).group_by(Analysis.analysis_type)
    if not is_admin:
        an_stmt = an_stmt.join(Experiment, Experiment.id == Analysis.experiment_id).join(Project, Project.id == Experiment.project_id).where(Project.owner_id == user.id)
    analyses_by_type = {row[0]: row[1] for row in db.execute(an_stmt).all()}

    return {
        "predictions_by_confidence": predictions_by_confidence,
        "experiments_by_status": experiments_by_status,
        "datasets_by_status": datasets_by_status,
        "analyses_by_type": analyses_by_type,
    }
