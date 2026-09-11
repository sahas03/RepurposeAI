import uuid

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import AuditAction
from app.core.exceptions import NotFoundError
from app.core.security import require_admin
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.user import UserOut, UserUpdateRequest
from app.services.audit_service import log_action
from app.services.auth_service import get_or_create_role
from app.utils.pagination import paginate

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("", summary="List all users (admin only)")
def list_users(
    page: int = 1, page_size: int = 20,
    db: Session = Depends(get_db), current_user: User = Depends(require_admin),
):
    params = PaginationParams(page=page, page_size=page_size)
    result = paginate(db, select(User).order_by(User.created_at.desc()), params, UserOut)
    return {"success": True, "data": result}


@router.get("/{user_id}", summary="Get a user by id (admin only)")
def get_user(user_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError("User was not found", code="USER_NOT_FOUND")
    return {"success": True, "data": UserOut.model_validate(user)}


@router.put("/{user_id}", summary="Update a user's role/active status (admin only)")
def update_user(user_id: uuid.UUID, payload: UserUpdateRequest, db: Session = Depends(get_db), current_user: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise NotFoundError("User was not found", code="USER_NOT_FOUND")
    if payload.name is not None:
        user.name = payload.name
    if payload.is_active is not None:
        user.is_active = payload.is_active
    if payload.role is not None:
        role = get_or_create_role(db, payload.role)
        user.role_id = role.id
        log_action(db, current_user.id, AuditAction.PERMISSION_CHANGE, "user", str(user.id), {"new_role": payload.role})
    db.flush()
    db.refresh(user)
    db.commit()
    return {"success": True, "data": UserOut.model_validate(user)}
