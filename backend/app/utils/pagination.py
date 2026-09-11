"""Generic pagination helper for SQLAlchemy queries."""
from typing import TypeVar

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from app.schemas.common import PaginatedResponse, PaginationParams

T = TypeVar("T")


def paginate(db: Session, stmt: Select, params: PaginationParams, schema) -> PaginatedResponse:
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    rows = db.execute(stmt.offset(params.offset).limit(params.page_size)).scalars().all()
    items = [schema.model_validate(row) for row in rows]
    return PaginatedResponse.build(items=items, total=total, page=params.page, page_size=params.page_size)
