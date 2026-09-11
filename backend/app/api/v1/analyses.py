import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.analysis import AnalysisOut, AnalysisRunRequest, AnalysisRunResponse
from app.services import analysis_service

router = APIRouter(prefix="/analyses", tags=["Analyses"])


@router.post("/run", status_code=202, summary="Queue a generic analysis job (gene_expression, dataset_quality, etc)")
def run_analysis(payload: AnalysisRunRequest, db: Session = Depends(get_db), current_user: User = Depends(require_permission("analysis:write"))):
    analysis, job_id = analysis_service.run_analysis(db, current_user, payload.experiment_id, payload.dataset_id, payload.analysis_type, payload.parameters)
    return {"success": True, "data": AnalysisRunResponse(job_id=job_id, analysis_id=analysis.id, status=analysis.status)}


@router.get("/{analysis_id}", summary="Get an analysis by id")
def get_analysis(analysis_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("analysis:read"))):
    analysis = analysis_service.get_analysis_or_404(db, analysis_id)
    return {"success": True, "data": AnalysisOut.model_validate(analysis)}
