import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.security import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import PaginationParams
from app.schemas.notification import NotificationOut
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("", summary="List the current user's notifications")
def list_notifications(page: int = 1, page_size: int = 20, db: Session = Depends(get_db), current_user: User = Depends(require_permission("notification:read"))):
    params = PaginationParams(page=page, page_size=page_size)
    result = notification_service.list_notifications(db, current_user.id, params)
    return {"success": True, "data": result}


@router.get("/unread", summary="List only unread notifications")
def unread_notifications(page: int = 1, page_size: int = 20, db: Session = Depends(get_db), current_user: User = Depends(require_permission("notification:read"))):
    params = PaginationParams(page=page, page_size=page_size)
    result = notification_service.list_notifications(db, current_user.id, params, unread_only=True)
    return {"success": True, "data": {"unread_count": notification_service.unread_count(db, current_user.id), **result.model_dump()}}


@router.put("/{notification_id}/read", summary="Mark a single notification as read")
def mark_read(notification_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("notification:read"))):
    notification = notification_service.mark_read(db, current_user.id, notification_id)
    db.commit()
    return {"success": True, "data": NotificationOut.model_validate(notification)}


@router.put("/read-all", summary="Mark all of the current user's notifications as read")
def mark_all_read(db: Session = Depends(get_db), current_user: User = Depends(require_permission("notification:read"))):
    count = notification_service.mark_all_read(db, current_user.id)
    db.commit()
    return {"success": True, "data": {"marked_read": count}}
