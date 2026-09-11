import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.constants import AuditAction, ExperimentStatus
from app.core.exceptions import AuthorizationError, NotFoundError
from app.models.analysis import Analysis
from app.models.dataset import Dataset
from app.models.experiment import Experiment
from app.models.prediction import Prediction
from app.models.project import Project
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.project import ProjectOut
from app.services.audit_service import log_action
from app.utils.pagination import paginate


def get_project_or_404(db: Session, project_id: uuid.UUID) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise NotFoundError("Project was not found", code="PROJECT_NOT_FOUND")
    return project


def ensure_project_access(project: Project, user: User) -> None:
    if user.role.name == "admin":
        return
    if project.owner_id != user.id:
        raise AuthorizationError("You do not have access to this project", code="PROJECT_ACCESS_DENIED")


def list_projects(db: Session, user: User, params: PaginationParams, status: str | None, search: str | None) -> PaginatedResponse[ProjectOut]:
    stmt = select(Project)
    if user.role.name != "admin":
        stmt = stmt.where(Project.owner_id == user.id)
    if status:
        stmt = stmt.where(Project.status == status)
    if search:
        stmt = stmt.where(or_(Project.name.ilike(f"%{search}%"), Project.description.ilike(f"%{search}%")))
    stmt = stmt.order_by(Project.created_at.desc())
    return paginate(db, stmt, params, ProjectOut)


def create_project(db: Session, user: User, name: str, description: str | None) -> Project:
    project = Project(owner_id=user.id, name=name, description=description)
    db.add(project)
    db.flush()
    db.refresh(project)
    log_action(db, user.id, AuditAction.PROJECT_CREATE, "project", str(project.id))
    return project


def update_project(db: Session, user: User, project_id: uuid.UUID, name: str | None, description: str | None, status: str | None) -> Project:
    project = get_project_or_404(db, project_id)
    ensure_project_access(project, user)
    if name is not None:
        project.name = name
    if description is not None:
        project.description = description
    if status is not None:
        project.status = status
    db.flush()
    db.refresh(project)
    log_action(db, user.id, AuditAction.PROJECT_UPDATE, "project", str(project.id))
    return project


def delete_project(db: Session, user: User, project_id: uuid.UUID) -> None:
    project = get_project_or_404(db, project_id)
    ensure_project_access(project, user)
    db.delete(project)
    db.flush()
    log_action(db, user.id, AuditAction.PROJECT_DELETE, "project", str(project_id))


def project_summary(db: Session, user: User, project_id: uuid.UUID) -> dict:
    project = get_project_or_404(db, project_id)
    ensure_project_access(project, user)

    experiment_count = db.scalar(select(func.count()).select_from(Experiment).where(Experiment.project_id == project_id)) or 0
    dataset_count = db.scalar(select(func.count()).select_from(Dataset).where(Dataset.project_id == project_id)) or 0
    analysis_count = db.scalar(
        select(func.count()).select_from(Analysis).join(Experiment).where(Experiment.project_id == project_id)
    ) or 0
    prediction_count = db.scalar(select(func.count()).select_from(Prediction).where(Prediction.project_id == project_id)) or 0
    completed = db.scalar(
        select(func.count()).select_from(Experiment).where(Experiment.project_id == project_id, Experiment.status == ExperimentStatus.COMPLETED.value)
    ) or 0
    running = db.scalar(
        select(func.count()).select_from(Experiment).where(Experiment.project_id == project_id, Experiment.status == ExperimentStatus.RUNNING.value)
    ) or 0
    failed = db.scalar(
        select(func.count()).select_from(Experiment).where(Experiment.project_id == project_id, Experiment.status == ExperimentStatus.FAILED.value)
    ) or 0
    high_confidence = db.scalar(
        select(func.count()).select_from(Prediction).where(Prediction.project_id == project_id, Prediction.confidence >= 0.75)
    ) or 0

    return {
        "project": project,
        "experiment_count": experiment_count,
        "dataset_count": dataset_count,
        "analysis_count": analysis_count,
        "prediction_count": prediction_count,
        "completed_experiments": completed,
        "running_experiments": running,
        "failed_experiments": failed,
        "high_confidence_predictions": high_confidence,
    }
