import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import PaginationParams
from app.schemas.disease import DiseaseOut
from app.services import disease_service

router = APIRouter(prefix="/diseases", tags=["Diseases"])


@router.get("", summary="List/search diseases")
def list_diseases(
    page: int = 1, page_size: int = 20, search: str | None = None, category: str | None = None,
    db: Session = Depends(get_db), current_user: User = Depends(require_permission("disease:read")),
):
    params = PaginationParams(page=page, page_size=page_size)
    result = disease_service.list_diseases(db, params, search, category)
    return {"success": True, "data": result}


@router.get("/{disease_id}", summary="Get a disease by id, including its associated-gene profile")
def get_disease(disease_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("disease:read"))):
    profile = disease_service.disease_profile(db, disease_id)
    from app.schemas.prediction import PredictionOut
    return {"success": True, "data": {
        "disease": DiseaseOut.model_validate(profile["disease"]),
        "associated_gene_count": profile["associated_gene_count"],
        "associated_genes": profile["associated_genes"],
        "has_predictions": profile["has_predictions"],
        "top_predictions": [PredictionOut.model_validate(p) for p in profile["top_predictions"]],
    }}
