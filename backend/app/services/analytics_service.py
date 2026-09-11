"""Date-range time-series aggregation for the analytics endpoints."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.dataset import Dataset
from app.models.experiment import Experiment
from app.models.prediction import Prediction
from app.models.project import Project
from app.models.user import User

RANGE_DAYS = {"7d": 7, "30d": 30, "90d": 90, "1y": 365}


def resolve_range(range_key: str, start: datetime | None = None, end: datetime | None = None) -> tuple[datetime, datetime]:
    now = datetime.now(timezone.utc)
    if range_key == "custom" and start and end:
        return start, end
    days = RANGE_DAYS.get(range_key, 30)
    return now - timedelta(days=days), now


def _daily_counts(db: Session, model, date_column, since: datetime, until: datetime, extra_filter=None) -> dict[str, int]:
    stmt = select(func.date(date_column), func.count()).where(date_column >= since, date_column <= until)
    if extra_filter is not None:
        stmt = stmt.where(extra_filter)
    stmt = stmt.group_by(func.date(date_column))
    rows = db.execute(stmt).all()
    return {str(row[0]): row[1] for row in rows}


def _fill_series(counts: dict[str, int], since: datetime, until: datetime) -> tuple[list[str], list[float]]:
    labels, series = [], []
    cursor = since.date()
    end_date = until.date()
    while cursor <= end_date:
        key = cursor.isoformat()
        labels.append(key)
        series.append(float(counts.get(key, 0)))
        cursor += timedelta(days=1)
    return labels, series


def experiments_analytics(db: Session, user: User, range_key: str) -> dict:
    since, until = resolve_range(range_key)
    stmt_filter = None if user.role.name == "admin" else Experiment.project_id.in_(select(Project.id).where(Project.owner_id == user.id))
    counts = _daily_counts(db, Experiment, Experiment.created_at, since, until, stmt_filter)
    labels, series = _fill_series(counts, since, until)
    total = sum(series)
    return {"range": range_key, "labels": labels, "series": {"experiments_created": series}, "summary": {"total": int(total)}}


def projects_analytics(db: Session, user: User, range_key: str) -> dict:
    since, until = resolve_range(range_key)
    stmt_filter = None if user.role.name == "admin" else Project.owner_id == user.id
    counts = _daily_counts(db, Project, Project.created_at, since, until, stmt_filter)
    labels, series = _fill_series(counts, since, until)
    return {"range": range_key, "labels": labels, "series": {"projects_created": series}, "summary": {"total": int(sum(series))}}


def predictions_analytics(db: Session, user: User, range_key: str) -> dict:
    since, until = resolve_range(range_key)
    stmt_filter = None if user.role.name == "admin" else Prediction.project_id.in_(select(Project.id).where(Project.owner_id == user.id))
    counts = _daily_counts(db, Prediction, Prediction.created_at, since, until, stmt_filter)
    labels, series = _fill_series(counts, since, until)

    avg_confidence_stmt = select(func.avg(Prediction.confidence)).where(Prediction.created_at >= since, Prediction.created_at <= until)
    if stmt_filter is not None:
        avg_confidence_stmt = avg_confidence_stmt.where(stmt_filter)
    avg_confidence = db.scalar(avg_confidence_stmt) or 0.0

    return {
        "range": range_key, "labels": labels, "series": {"predictions_generated": series},
        "summary": {"total": int(sum(series)), "average_confidence": round(float(avg_confidence), 4)},
    }


def datasets_analytics(db: Session, user: User, range_key: str) -> dict:
    since, until = resolve_range(range_key)
    stmt_filter = None if user.role.name == "admin" else Dataset.project_id.in_(select(Project.id).where(Project.owner_id == user.id))
    counts = _daily_counts(db, Dataset, Dataset.created_at, since, until, stmt_filter)
    labels, series = _fill_series(counts, since, until)
    return {"range": range_key, "labels": labels, "series": {"datasets_uploaded": series}, "summary": {"total": int(sum(series))}}


def activity_analytics(db: Session, user: User, range_key: str) -> dict:
    from app.models.audit_log import AuditLog

    since, until = resolve_range(range_key)
    stmt_filter = None if user.role.name == "admin" else AuditLog.user_id == user.id
    counts = _daily_counts(db, AuditLog, AuditLog.timestamp, since, until, stmt_filter)
    labels, series = _fill_series(counts, since, until)
    return {"range": range_key, "labels": labels, "series": {"actions": series}, "summary": {"total": int(sum(series))}}
