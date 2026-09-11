import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import PaginationParams
from app.schemas.compound import CompoundOut
from app.services import compound_service

router = APIRouter(prefix="/compounds", tags=["Compounds"])


@router.get("", summary="List/search compounds")
def list_compounds(
    page: int = 1, page_size: int = 20, search: str | None = None, drug_id: uuid.UUID | None = None,
    db: Session = Depends(get_db), current_user: User = Depends(require_permission("compound:read")),
):
    params = PaginationParams(page=page, page_size=page_size)
    result = compound_service.list_compounds(db, params, search, drug_id)
    return {"success": True, "data": result}


@router.get("/{compound_id}", summary="Get a compound by id")
def get_compound(compound_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("compound:read"))):
    compound = compound_service.get_compound_or_404(db, compound_id)
    return {"success": True, "data": CompoundOut.model_validate(compound)}
