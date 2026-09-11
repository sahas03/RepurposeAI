import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import PaginationParams
from app.schemas.gene import TargetOut
from app.services import gene_service

router = APIRouter(prefix="/targets", tags=["Targets"])


@router.get("", summary="List/search targets")
def list_targets(
    page: int = 1, page_size: int = 20, search: str | None = None,
    target_type: str | None = None, gene_id: uuid.UUID | None = None,
    db: Session = Depends(get_db), current_user: User = Depends(require_permission("target:read")),
):
    params = PaginationParams(page=page, page_size=page_size)
    result = gene_service.list_targets(db, params, search, target_type, gene_id)
    return {"success": True, "data": result}


@router.get("/{target_id}", summary="Get a target by id")
def get_target(target_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("target:read"))):
    target = gene_service.get_target_or_404(db, target_id)
    return {"success": True, "data": TargetOut.model_validate(target)}
