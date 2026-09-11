import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.disease import Disease
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.disease import DiseaseOut
from app.utils.pagination import paginate
from app.biotech.disease_analysis import get_disease_or_404, disease_profile  # noqa: F401 - re-exported


def list_diseases(db: Session, params: PaginationParams, search: str | None, category: str | None) -> PaginatedResponse[DiseaseOut]:
    stmt = select(Disease)
    if search:
        stmt = stmt.where(or_(Disease.name.ilike(f"%{search}%"), Disease.description.ilike(f"%{search}%")))
    if category:
        stmt = stmt.where(Disease.category == category)
    stmt = stmt.order_by(Disease.name.asc())
    return paginate(db, stmt, params, DiseaseOut)
