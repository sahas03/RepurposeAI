from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import PaginationParams
from app.services import gene_service

router = APIRouter(prefix="/interactions", tags=["Interactions"])


@router.get("", summary="List/filter interaction records (drug-target, gene-disease, etc)")
def list_interactions(
    page: int = 1, page_size: int = 20, interaction_type: str | None = None,
    source_type: str | None = None, target_type: str | None = None, min_confidence: float | None = None,
    db: Session = Depends(get_db), current_user: User = Depends(require_permission("interaction:read")),
):
    params = PaginationParams(page=page, page_size=page_size)
    result = gene_service.list_interactions(db, params, interaction_type, source_type, target_type, min_confidence)
    return {"success": True, "data": result}
