from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import AnalyticsSeries
from app.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["Analytics"])

RangeQuery = Query(default="30d", pattern="^(7d|30d|90d|1y|custom)$")


@router.get("/experiments", summary="Experiment creation volume over a date range")
def experiments_analytics(range: str = RangeQuery, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    data = analytics_service.experiments_analytics(db, current_user, range)
    return {"success": True, "data": AnalyticsSeries(**data)}


@router.get("/projects", summary="Project creation volume over a date range")
def projects_analytics(range: str = RangeQuery, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    data = analytics_service.projects_analytics(db, current_user, range)
    return {"success": True, "data": AnalyticsSeries(**data)}


@router.get("/predictions", summary="Prediction generation volume and average confidence over a date range")
def predictions_analytics(range: str = RangeQuery, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    data = analytics_service.predictions_analytics(db, current_user, range)
    return {"success": True, "data": AnalyticsSeries(**data)}


@router.get("/datasets", summary="Dataset upload volume over a date range")
def datasets_analytics(range: str = RangeQuery, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    data = analytics_service.datasets_analytics(db, current_user, range)
    return {"success": True, "data": AnalyticsSeries(**data)}


@router.get("/activity", summary="Audit log activity volume over a date range")
def activity_analytics(range: str = RangeQuery, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    data = analytics_service.activity_analytics(db, current_user, range)
    return {"success": True, "data": AnalyticsSeries(**data)}
