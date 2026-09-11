from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.search import SearchResults
from app.services import search_service

router = APIRouter(prefix="/search", tags=["Search"])


@router.get("", summary="Global search across drugs, diseases, genes, compounds, projects, experiments, and datasets")
def search(q: str = Query(min_length=1), db: Session = Depends(get_db), current_user: User = Depends(require_permission("search:read"))):
    data = search_service.global_search(db, current_user, q)
    return {"success": True, "data": SearchResults(**data)}
