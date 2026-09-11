import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import (
    ACTIVE_EXPERIMENT_STATUSES,
    AuditAction,
    ExperimentStatus,
    ExperimentType,
    JobType,
)
from app.core.exceptions import ConflictError, NotFoundError, ValidationAppError
from app.models.experiment import Experiment
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.experiment import ExperimentOut
from app.services.audit_service import log_action
from app.services.project_service import ensure_project_access, get_project_or_404
from app.utils.pagination import paginate


def get_experiment_or_404(db: Session, experiment_id: uuid.UUID) -> Experiment:
    experiment = db.get(Experiment, experiment_id)
    if not experiment:
        raise NotFoundError("Experiment was not found", code="EXPERIMENT_NOT_FOUND")
    return experiment


def check_experiment_access(db: Session, user: User, experiment: Experiment) -> None:
    project = get_project_or_404(db, experiment.project_id)
    ensure_project_access(project, user)


def list_experiments(db: Session, user: User, params: PaginationParams, project_id: uuid.UUID | None, status: str | None, experiment_type: str | None) -> PaginatedResponse[ExperimentOut]:
    stmt = select(Experiment)
    if user.role.name != "admin":
        from app.models.project import Project
        stmt = stmt.join(Project, Project.id == Experiment.project_id).where(Project.owner_id == user.id)
    if project_id:
        stmt = stmt.where(Experiment.project_id == project_id)
    if status:
        stmt = stmt.where(Experiment.status == status)
    if experiment_type:
        stmt = stmt.where(Experiment.experiment_type == experiment_type)
    stmt = stmt.order_by(Experiment.created_at.desc())
    return paginate(db, stmt, params, ExperimentOut)


def create_experiment(db: Session, user: User, project_id: uuid.UUID, name: str, description: str | None, experiment_type: ExperimentType, parameters: dict) -> Experiment:
    project = get_project_or_404(db, project_id)
    ensure_project_access(project, user)

    experiment = Experiment(
        project_id=project_id,
        name=name,
        description=description,
        experiment_type=experiment_type.value,
        status=ExperimentStatus.DRAFT.value,
        parameters=parameters,
    )
    db.add(experiment)
    db.flush()
    db.refresh(experiment)
    log_action(db, user.id, AuditAction.EXPERIMENT_CREATE, "experiment", str(experiment.id))
    return experiment


def update_experiment(db: Session, user: User, experiment_id: uuid.UUID, name: str | None, description: str | None, parameters: dict | None, status: str | None) -> Experiment:
    experiment = get_experiment_or_404(db, experiment_id)
    check_experiment_access(db, user, experiment)
    if name is not None:
        experiment.name = name
    if description is not None:
        experiment.description = description
    if parameters is not None:
        experiment.parameters = parameters
    if status is not None:
        experiment.status = status
    db.flush()
    db.refresh(experiment)
    return experiment


def delete_experiment(db: Session, user: User, experiment_id: uuid.UUID) -> None:
    experiment = get_experiment_or_404(db, experiment_id)
    check_experiment_access(db, user, experiment)
    db.delete(experiment)
    db.flush()


def start_experiment(db: Session, user: User, experiment_id: uuid.UUID) -> Experiment:
    experiment = get_experiment_or_404(db, experiment_id)
    check_experiment_access(db, user, experiment)

    if experiment.status in {s.value for s in ACTIVE_EXPERIMENT_STATUSES}:
        raise ConflictError("Experiment is already running", code="EXPERIMENT_ALREADY_RUNNING")

    experiment.status = ExperimentStatus.QUEUED.value
    experiment.progress = 0
    db.flush()
    db.refresh(experiment)
    log_action(db, user.id, AuditAction.EXPERIMENT_START, "experiment", str(experiment.id))

    db.commit()

    from app.workers.analysis_tasks import run_experiment_task
    run_experiment_task.delay(str(experiment.id), str(user.id))

    db.refresh(experiment)
    return experiment


def cancel_experiment(db: Session, user: User, experiment_id: uuid.UUID) -> Experiment:
    experiment = get_experiment_or_404(db, experiment_id)
    check_experiment_access(db, user, experiment)

    if experiment.status not in {s.value for s in ACTIVE_EXPERIMENT_STATUSES}:
        raise ValidationAppError("Only queued/running experiments can be cancelled", code="EXPERIMENT_NOT_CANCELLABLE")

    experiment.status = ExperimentStatus.CANCELLED.value
    db.flush()
    db.refresh(experiment)
    log_action(db, user.id, AuditAction.EXPERIMENT_CANCEL, "experiment", str(experiment.id))

    from app.websocket.handlers import publish_ws_event
    publish_ws_event(f"experiments:{experiment.id}", {
        "event": "failed", "status": experiment.status, "progress": experiment.progress,
        "message": "Experiment cancelled by user",
    })
    return experiment


def get_experiment_results(db: Session, user: User, experiment_id: uuid.UUID) -> dict:
    experiment = get_experiment_or_404(db, experiment_id)
    check_experiment_access(db, user, experiment)
    from app.models.analysis import Analysis
    from app.models.prediction import Prediction

    analyses = db.scalars(select(Analysis).where(Analysis.experiment_id == experiment_id)).all()
    predictions = db.scalars(
        select(Prediction).where(Prediction.experiment_id == experiment_id).order_by(Prediction.rank.asc())
    ).all()
    return {"experiment": experiment, "analyses": analyses, "predictions": predictions}
