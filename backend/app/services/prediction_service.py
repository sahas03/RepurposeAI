import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import AuditAction, JobStatus, JobType
from app.core.exceptions import NotFoundError
from app.models.job import Job
from app.models.prediction import Prediction
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.prediction import PredictionOut
from app.services.audit_service import log_action
from app.services.job_service import create_job, get_job_or_404
from app.services.project_service import ensure_project_access, get_project_or_404
from app.utils.pagination import paginate


def start_repurposing_run(db: Session, user: User, disease_id: uuid.UUID, project_id: uuid.UUID | None, experiment_id: uuid.UUID | None, parameters: dict) -> Job:
    if project_id:
        project = get_project_or_404(db, project_id)
        ensure_project_access(project, user)

    job = create_job(
        db, JobType.DRUG_REPURPOSING, user_id=user.id, project_id=project_id, experiment_id=experiment_id,
    )
    job.result = {"disease_id": str(disease_id), "parameters": parameters}
    db.flush()
    log_action(db, user.id, AuditAction.PREDICTION_GENERATE, "job", str(job.id), {"disease_id": str(disease_id)})
    db.commit()

    from app.workers.prediction_tasks import run_repurposing_task
    run_repurposing_task.delay(str(job.id), str(disease_id), str(user.id), str(project_id) if project_id else None, str(experiment_id) if experiment_id else None, parameters)

    db.refresh(job)
    return job


def get_repurposing_job(db: Session, job_id: uuid.UUID) -> Job:
    return get_job_or_404(db, job_id)


def get_repurposing_results(db: Session, job_id: uuid.UUID) -> dict:
    job = get_job_or_404(db, job_id)
    predictions: list[Prediction] = []
    disease_id = None
    if job.result:
        disease_id = job.result.get("disease_id")
        prediction_ids = job.result.get("prediction_ids", [])
        if prediction_ids:
            predictions = list(db.scalars(select(Prediction).where(Prediction.id.in_(prediction_ids)).order_by(Prediction.rank.asc())).all())
    return {"job_id": job.id, "status": job.status, "disease_id": disease_id, "predictions": predictions}


def list_predictions(db: Session, params: PaginationParams, project_id: uuid.UUID | None, disease_id: uuid.UUID | None, drug_id: uuid.UUID | None, min_confidence: float | None) -> PaginatedResponse[PredictionOut]:
    stmt = select(Prediction)
    if project_id:
        stmt = stmt.where(Prediction.project_id == project_id)
    if disease_id:
        stmt = stmt.where(Prediction.disease_id == disease_id)
    if drug_id:
        stmt = stmt.where(Prediction.drug_id == drug_id)
    if min_confidence is not None:
        stmt = stmt.where(Prediction.confidence >= min_confidence)
    stmt = stmt.order_by(Prediction.score.desc())
    return paginate(db, stmt, params, PredictionOut)
