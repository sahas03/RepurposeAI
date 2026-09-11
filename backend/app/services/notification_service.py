"""Creates notifications and pushes them live over /ws/notifications."""
import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.constants import NotificationType
from app.core.exceptions import NotFoundError
from app.models.notification import Notification
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.notification import NotificationOut
from app.utils.pagination import paginate


def create_notification(
    db: Session,
    user_id: uuid.UUID,
    title: str,
    message: str,
    notification_type: NotificationType | str,
    metadata: dict | None = None,
) -> Notification:
    from app.websocket.handlers import publish_ws_event

    type_value = notification_type.value if isinstance(notification_type, NotificationType) else notification_type
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=type_value,
        extra_metadata=metadata or {},
    )
    db.add(notification)
    db.flush()
    db.refresh(notification)

    publish_ws_event(
        f"notifications:{user_id}",
        {
            "event": "notification",
            "notification_id": str(notification.id),
            "title": title,
            "message": message,
            "notification_type": type_value,
        },
    )
    return notification


def list_notifications(db: Session, user_id: uuid.UUID, params: PaginationParams, unread_only: bool = False) -> PaginatedResponse[NotificationOut]:
    stmt = select(Notification).where(Notification.user_id == user_id)
    if unread_only:
        stmt = stmt.where(Notification.read.is_(False))
    stmt = stmt.order_by(Notification.created_at.desc())
    return paginate(db, stmt, params, NotificationOut)


def unread_count(db: Session, user_id: uuid.UUID) -> int:
    return db.scalar(
        select(func.count()).select_from(Notification).where(Notification.user_id == user_id, Notification.read.is_(False))
    ) or 0


def mark_read(db: Session, user_id: uuid.UUID, notification_id: uuid.UUID) -> Notification:
    notification = db.get(Notification, notification_id)
    if not notification or notification.user_id != user_id:
        raise NotFoundError("Notification was not found", code="NOTIFICATION_NOT_FOUND")
    notification.read = True
    db.flush()
    db.refresh(notification)
    return notification


def mark_all_read(db: Session, user_id: uuid.UUID) -> int:
    notifications = db.scalars(select(Notification).where(Notification.user_id == user_id, Notification.read.is_(False))).all()
    for n in notifications:
        n.read = True
    db.flush()
    return len(notifications)
