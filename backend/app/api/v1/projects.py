import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user, require_permission
from app.db.session import get_db
from app.models.analysis import Analysis
from app.models.dataset import Dataset
from app.models.experiment import Experiment
from app.models.prediction import Prediction
from app.models.user import User
from app.schemas.common import PaginationParams
from app.schemas.dataset import DatasetOut
from app.schemas.experiment import ExperimentOut
from app.schemas.prediction import PredictionOut
from app.schemas.project import ProjectCreate, ProjectOut, ProjectSummary, ProjectUpdate
from app.services import project_service
from app.utils.pagination import paginate

router = APIRouter(prefix="/projects", tags=["Projects"])


@router.get("", summary="List projects owned by the current user (or all, for admins)")
def list_projects(
    page: int = 1, page_size: int = 20, status: str | None = None, search: str | None = None,
    db: Session = Depends(get_db), current_user: User = Depends(require_permission("project:read")),
):
    params = PaginationParams(page=page, page_size=page_size)
    result = project_service.list_projects(db, current_user, params, status, search)
    return {"success": True, "data": result}


@router.post("", status_code=201, summary="Create a new project")
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("project:write"))):
    project = project_service.create_project(db, current_user, payload.name, payload.description)
    db.commit()
    return {"success": True, "data": ProjectOut.model_validate(project)}


@router.get("/{project_id}", summary="Get a project by id")
def get_project(project_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("project:read"))):
    project = project_service.get_project_or_404(db, project_id)
    project_service.ensure_project_access(project, current_user)
    return {"success": True, "data": ProjectOut.model_validate(project)}


@router.put("/{project_id}", summary="Update a project")
def update_project(project_id: uuid.UUID, payload: ProjectUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("project:write"))):
    status_value = payload.status.value if payload.status else None
    project = project_service.update_project(db, current_user, project_id, payload.name, payload.description, status_value)
    db.commit()
    return {"success": True, "data": ProjectOut.model_validate(project)}


@router.delete("/{project_id}", summary="Delete a project and all of its data")
def delete_project(project_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("project:delete"))):
    project_service.delete_project(db, current_user, project_id)
    db.commit()
    return {"success": True, "data": {"message": "Project deleted"}}


@router.get("/{project_id}/summary", summary="Get aggregated counts and stats for a project")
def project_summary(project_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("project:read"))):
    summary = project_service.project_summary(db, current_user, project_id)
    return {"success": True, "data": ProjectSummary(
        project=ProjectOut.model_validate(summary["project"]),
        experiment_count=summary["experiment_count"],
        dataset_count=summary["dataset_count"],
        analysis_count=summary["analysis_count"],
        prediction_count=summary["prediction_count"],
        completed_experiments=summary["completed_experiments"],
        running_experiments=summary["running_experiments"],
        failed_experiments=summary["failed_experiments"],
        high_confidence_predictions=summary["high_confidence_predictions"],
    )}


@router.get("/{project_id}/experiments", summary="List experiments belonging to a project")
def project_experiments(project_id: uuid.UUID, page: int = 1, page_size: int = 20, db: Session = Depends(get_db), current_user: User = Depends(require_permission("project:read"))):
    project = project_service.get_project_or_404(db, project_id)
    project_service.ensure_project_access(project, current_user)
    params = PaginationParams(page=page, page_size=page_size)
    result = paginate(db, select(Experiment).where(Experiment.project_id == project_id).order_by(Experiment.created_at.desc()), params, ExperimentOut)
    return {"success": True, "data": result}


@router.get("/{project_id}/datasets", summary="List datasets belonging to a project")
def project_datasets(project_id: uuid.UUID, page: int = 1, page_size: int = 20, db: Session = Depends(get_db), current_user: User = Depends(require_permission("project:read"))):
    project = project_service.get_project_or_404(db, project_id)
    project_service.ensure_project_access(project, current_user)
    params = PaginationParams(page=page, page_size=page_size)
    result = paginate(db, select(Dataset).where(Dataset.project_id == project_id).order_by(Dataset.created_at.desc()), params, DatasetOut)
    return {"success": True, "data": result}


@router.get("/{project_id}/analyses", summary="List analyses belonging to a project's experiments")
def project_analyses(project_id: uuid.UUID, page: int = 1, page_size: int = 20, db: Session = Depends(get_db), current_user: User = Depends(require_permission("project:read"))):
    project = project_service.get_project_or_404(db, project_id)
    project_service.ensure_project_access(project, current_user)
    params = PaginationParams(page=page, page_size=page_size)
    from app.schemas.analysis import AnalysisOut
    stmt = select(Analysis).join(Experiment).where(Experiment.project_id == project_id).order_by(Analysis.created_at.desc())
    result = paginate(db, stmt, params, AnalysisOut)
    return {"success": True, "data": result}


@router.get("/{project_id}/predictions", summary="List predictions belonging to a project")
def project_predictions(project_id: uuid.UUID, page: int = 1, page_size: int = 20, db: Session = Depends(get_db), current_user: User = Depends(require_permission("project:read"))):
    project = project_service.get_project_or_404(db, project_id)
    project_service.ensure_project_access(project, current_user)
    params = PaginationParams(page=page, page_size=page_size)
    stmt = select(Prediction).where(Prediction.project_id == project_id).order_by(Prediction.score.desc())
    result = paginate(db, stmt, params, PredictionOut)
    return {"success": True, "data": result}
