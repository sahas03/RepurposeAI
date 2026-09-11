from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db

router = APIRouter(prefix="/health", tags=["Health"])


@router.get("", summary="API liveness check")
def health():
    return {"success": True, "data": {"status": "ok", "service": settings.PROJECT_NAME, "version": settings.APP_VERSION}}


@router.get("/database", summary="Database connectivity check")
def health_database(db: Session = Depends(get_db)):
    try:
        db.execute(select(1))
        return {"success": True, "data": {"status": "healthy"}}
    except Exception as exc:
        return {"success": False, "error": {"code": "DATABASE_UNHEALTHY", "message": str(exc), "details": {}}}


@router.get("/redis", summary="Redis connectivity check")
def health_redis():
    try:
        import redis as redis_lib
        client = redis_lib.Redis.from_url(settings.REDIS_URL, socket_connect_timeout=2)
        client.ping()
        return {"success": True, "data": {"status": "healthy"}}
    except Exception as exc:
        return {"success": False, "error": {"code": "REDIS_UNHEALTHY", "message": str(exc), "details": {}}}
