import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import NotFoundError
from app.models.compound import Compound
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.compound import CompoundOut
from app.utils.pagination import paginate


def list_compounds(db: Session, params: PaginationParams, search: str | None, drug_id: uuid.UUID | None) -> PaginatedResponse[CompoundOut]:
    stmt = select(Compound)
    if search:
        stmt = stmt.where(Compound.name.ilike(f"%{search}%"))
    if drug_id:
        stmt = stmt.where(Compound.drug_id == drug_id)
    stmt = stmt.order_by(Compound.name.asc())
    return paginate(db, stmt, params, CompoundOut)


def get_compound_or_404(db: Session, compound_id: uuid.UUID) -> Compound:
    compound = db.get(Compound, compound_id)
    if not compound:
        raise NotFoundError("Compound was not found", code="COMPOUND_NOT_FOUND")
    return compound
