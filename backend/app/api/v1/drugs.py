import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import PaginationParams
from app.schemas.drug import DrugOut
from app.services import drug_service

router = APIRouter(prefix="/drugs", tags=["Drugs"])


@router.get("", summary="List/search drugs")
def list_drugs(
    page: int = 1, page_size: int = 20, search: str | None = None,
    drug_class: str | None = None, approval_status: str | None = None,
    db: Session = Depends(get_db), current_user: User = Depends(require_permission("drug:read")),
):
    params = PaginationParams(page=page, page_size=page_size)
    result = drug_service.list_drugs(db, params, search, drug_class, approval_status)
    return {"success": True, "data": result}


@router.get("/{drug_id}", summary="Get a drug by id")
def get_drug(drug_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("drug:read"))):
    drug = drug_service.get_drug_or_404(db, drug_id)
    return {"success": True, "data": DrugOut.model_validate(drug)}
