from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.dashboard import ActivityItem, DashboardMetrics, DashboardOverview, SystemStatus
from app.schemas.experiment import ExperimentOut
from app.schemas.prediction import PredictionOut
from app.services import dashboard_service

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get("/overview", summary="Aggregated counts for the main dashboard")
def overview(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    data = dashboard_service.dashboard_overview(db, current_user)
    return {"success": True, "data": DashboardOverview(**data)}


@router.get("/activity", summary="Recent activity feed (from the audit log)")
def activity(limit: int = 20, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    data = dashboard_service.recent_activity(db, current_user, limit)
    return {"success": True, "data": [ActivityItem(**item) for item in data]}


@router.get("/recent-experiments", summary="Most recently created experiments")
def recent_experiments(limit: int = 10, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    data = dashboard_service.recent_experiments(db, current_user, limit)
    return {"success": True, "data": [ExperimentOut.model_validate(e) for e in data]}


@router.get("/recent-predictions", summary="Most recently generated predictions")
def recent_predictions(limit: int = 10, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    data = dashboard_service.recent_predictions(db, current_user, limit)
    return {"success": True, "data": [PredictionOut.model_validate(p) for p in data]}


@router.get("/system-status", summary="Health of database/redis/celery and process uptime")
def status_(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    data = dashboard_service.system_status(db)
    return {"success": True, "data": SystemStatus(**data)}


@router.get("/metrics", summary="Breakdown metrics for dashboard charts")
def metrics(db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    data = dashboard_service.dashboard_metrics(db, current_user)
    return {"success": True, "data": DashboardMetrics(**data)}
