import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import PaginationParams
from app.schemas.job import JobOut
from app.schemas.prediction import (
    PredictionOut,
    RepurposingResultsOut,
    RepurposingRunRequest,
    RepurposingRunResponse,
)
from app.services import prediction_service

repurposing_router = APIRouter(prefix="/repurposing", tags=["Repurposing"])
predictions_router = APIRouter(prefix="/predictions", tags=["Predictions"])


@repurposing_router.post("/run", status_code=202, summary="Run the drug repurposing pipeline for a disease")
def run_repurposing(payload: RepurposingRunRequest, db: Session = Depends(get_db), current_user: User = Depends(require_permission("repurposing:run"))):
    job = prediction_service.start_repurposing_run(db, current_user, payload.disease_id, payload.project_id, payload.experiment_id, payload.parameters)
    return {"success": True, "data": RepurposingRunResponse(job_id=job.id, status=job.status)}


@repurposing_router.get("/{job_id}", summary="Poll the status of a repurposing run")
def get_repurposing_job(job_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("prediction:read"))):
    job = prediction_service.get_repurposing_job(db, job_id)
    return {"success": True, "data": JobOut.model_validate(job)}


@repurposing_router.get("/{job_id}/results", summary="Get the ranked, explained predictions from a completed repurposing run")
def get_repurposing_results(job_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("prediction:read"))):
    data = prediction_service.get_repurposing_results(db, job_id)
    return {"success": True, "data": RepurposingResultsOut(
        job_id=data["job_id"], status=data["status"], disease_id=data["disease_id"],
        predictions=[PredictionOut.model_validate(p) for p in data["predictions"]],
    )}


@predictions_router.get("", summary="List/filter drug repurposing predictions")
def list_predictions(
    page: int = 1, page_size: int = 20, project_id: uuid.UUID | None = None,
    disease_id: uuid.UUID | None = None, drug_id: uuid.UUID | None = None, min_confidence: float | None = None,
    db: Session = Depends(get_db), current_user: User = Depends(require_permission("prediction:read")),
):
    params = PaginationParams(page=page, page_size=page_size)
    result = prediction_service.list_predictions(db, params, project_id, disease_id, drug_id, min_confidence)
    return {"success": True, "data": result}
