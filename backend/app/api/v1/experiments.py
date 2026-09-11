import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import PaginationParams
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentOut,
    ExperimentResultsOut,
    ExperimentStatusOut,
    ExperimentUpdate,
)
from app.schemas.analysis import AnalysisOut
from app.schemas.prediction import PredictionOut
from app.services import experiment_service

router = APIRouter(prefix="/experiments", tags=["Experiments"])


@router.get("", summary="List experiments")
def list_experiments(
    page: int = 1, page_size: int = 20, project_id: uuid.UUID | None = None,
    status: str | None = None, experiment_type: str | None = None,
    db: Session = Depends(get_db), current_user: User = Depends(require_permission("experiment:read")),
):
    params = PaginationParams(page=page, page_size=page_size)
    result = experiment_service.list_experiments(db, current_user, params, project_id, status, experiment_type)
    return {"success": True, "data": result}


@router.post("", status_code=201, summary="Create a new experiment")
def create_experiment(payload: ExperimentCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("experiment:write"))):
    experiment = experiment_service.create_experiment(
        db, current_user, payload.project_id, payload.name, payload.description, payload.experiment_type, payload.parameters
    )
    db.commit()
    return {"success": True, "data": ExperimentOut.model_validate(experiment)}


@router.get("/{experiment_id}", summary="Get an experiment by id")
def get_experiment(experiment_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("experiment:read"))):
    experiment = experiment_service.get_experiment_or_404(db, experiment_id)
    experiment_service.check_experiment_access(db, current_user, experiment)
    return {"success": True, "data": ExperimentOut.model_validate(experiment)}


@router.put("/{experiment_id}", summary="Update an experiment")
def update_experiment(experiment_id: uuid.UUID, payload: ExperimentUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("experiment:write"))):
    status_value = payload.status.value if payload.status else None
    experiment = experiment_service.update_experiment(db, current_user, experiment_id, payload.name, payload.description, payload.parameters, status_value)
    db.commit()
    return {"success": True, "data": ExperimentOut.model_validate(experiment)}


@router.delete("/{experiment_id}", summary="Delete an experiment")
def delete_experiment(experiment_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("experiment:delete"))):
    experiment_service.delete_experiment(db, current_user, experiment_id)
    db.commit()
    return {"success": True, "data": {"message": "Experiment deleted"}}


@router.post("/{experiment_id}/start", summary="Queue an experiment for background execution")
def start_experiment(experiment_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("experiment:write"))):
    experiment = experiment_service.start_experiment(db, current_user, experiment_id)
    return {"success": True, "data": ExperimentOut.model_validate(experiment)}


@router.post("/{experiment_id}/cancel", summary="Cancel a queued or running experiment")
def cancel_experiment(experiment_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("experiment:write"))):
    experiment = experiment_service.cancel_experiment(db, current_user, experiment_id)
    db.commit()
    return {"success": True, "data": ExperimentOut.model_validate(experiment)}


@router.get("/{experiment_id}/status", summary="Poll experiment lifecycle status and progress")
def experiment_status(experiment_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("experiment:read"))):
    experiment = experiment_service.get_experiment_or_404(db, experiment_id)
    experiment_service.check_experiment_access(db, current_user, experiment)
    return {"success": True, "data": ExperimentStatusOut.model_validate(experiment)}


@router.get("/{experiment_id}/results", summary="Get an experiment's analyses and predictions")
def experiment_results(experiment_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("experiment:read"))):
    data = experiment_service.get_experiment_results(db, current_user, experiment_id)
    payload = ExperimentResultsOut(
        id=data["experiment"].id,
        status=data["experiment"].status,
        analyses=[AnalysisOut.model_validate(a).model_dump(mode="json") for a in data["analyses"]],
        predictions=[PredictionOut.model_validate(p).model_dump(mode="json") for p in data["predictions"]],
    )
    return {"success": True, "data": payload}
