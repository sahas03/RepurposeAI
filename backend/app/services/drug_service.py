import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.drug import Drug
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.drug import DrugOut
from app.utils.pagination import paginate


def list_drugs(db: Session, params: PaginationParams, search: str | None, drug_class: str | None, approval_status: str | None) -> PaginatedResponse[DrugOut]:
    stmt = select(Drug)
    if search:
        stmt = stmt.where(or_(Drug.name.ilike(f"%{search}%"), Drug.generic_name.ilike(f"%{search}%")))
    if drug_class:
        stmt = stmt.where(Drug.drug_class == drug_class)
    if approval_status:
        stmt = stmt.where(Drug.approval_status == approval_status)
    stmt = stmt.order_by(Drug.name.asc())
    return paginate(db, stmt, params, DrugOut)


def get_drug_or_404(db: Session, drug_id: uuid.UUID) -> Drug:
    drug = db.get(Drug, drug_id)
    if not drug:
        raise NotFoundError("Drug was not found", code="DRUG_NOT_FOUND")
    return drug
