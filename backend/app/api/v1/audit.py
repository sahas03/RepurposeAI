import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import require_admin
from app.db.session import get_db
from app.models.audit_log import AuditLog
from app.models.user import User
from app.schemas.audit import AuditLogOut
from app.schemas.common import PaginationParams
from app.utils.pagination import paginate

router = APIRouter(prefix="/audit-logs", tags=["Audit"])


@router.get("", summary="List audit log entries (admin only)")
def list_audit_logs(
    page: int = 1, page_size: int = 20, action: str | None = None,
    resource_type: str | None = None, user_id: uuid.UUID | None = None,
    db: Session = Depends(get_db), current_user: User = Depends(require_admin),
):
    stmt = select(AuditLog)
    if action:
        stmt = stmt.where(AuditLog.action == action)
    if resource_type:
        stmt = stmt.where(AuditLog.resource_type == resource_type)
    if user_id:
        stmt = stmt.where(AuditLog.user_id == user_id)
    stmt = stmt.order_by(AuditLog.timestamp.desc())
    params = PaginationParams(page=page, page_size=page_size)
    result = paginate(db, stmt, params, AuditLogOut)
    return {"success": True, "data": result}
