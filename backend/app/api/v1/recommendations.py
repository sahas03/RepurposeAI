import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import PaginationParams
from app.schemas.recommendation import (
    RecommendationGenerateRequest,
    RecommendationOut,
    RecommendationUpdate,
)
from app.services import recommendation_service

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


@router.get("", summary="List the current user's recommendations")
def list_recommendations(
    page: int = 1, page_size: int = 20, status: str | None = None,
    db: Session = Depends(get_db), current_user: User = Depends(require_permission("recommendation:read")),
):
    params = PaginationParams(page=page, page_size=page_size)
    result = recommendation_service.list_recommendations(db, current_user, params, status)
    return {"success": True, "data": result}


@router.post("/generate", summary="Scan the user's projects and generate fresh recommendations")
def generate_recommendations(payload: RecommendationGenerateRequest, db: Session = Depends(get_db), current_user: User = Depends(require_permission("recommendation:read"))):
    recs = recommendation_service.generate_recommendations(db, current_user, payload.project_id)
    db.commit()
    return {"success": True, "data": [RecommendationOut.model_validate(r) for r in recs]}


@router.put("/{recommendation_id}", summary="Update a recommendation's status/priority")
def update_recommendation(recommendation_id: uuid.UUID, payload: RecommendationUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_permission("recommendation:write"))):
    rec = recommendation_service.update_recommendation(db, current_user, recommendation_id, payload.status, payload.priority)
    db.commit()
    return {"success": True, "data": RecommendationOut.model_validate(rec)}


@router.post("/{recommendation_id}/dismiss", summary="Dismiss a recommendation")
def dismiss_recommendation(recommendation_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("recommendation:read"))):
    rec = recommendation_service.dismiss_recommendation(db, current_user, recommendation_id)
    db.commit()
    return {"success": True, "data": RecommendationOut.model_validate(rec)}
