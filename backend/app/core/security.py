"""Password hashing, JWT issuance/verification, and auth dependencies."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from fastapi import Depends, WebSocket, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import ROLE_PERMISSIONS
from app.core.exceptions import AuthenticationError, AuthorizationError
from app.db.session import get_db
from app.models.user import User

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login", auto_error=False
)

TOKEN_TYPE_ACCESS = "access"
TOKEN_TYPE_REFRESH = "refresh"


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


def _create_token(subject: str, token_type: str, expires_delta: timedelta, extra_claims: Optional[dict] = None) -> str:
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
        "jti": str(uuid.uuid4()),
    }
    if extra_claims:
        payload.update(extra_claims)
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: uuid.UUID | str, role: str) -> str:
    return _create_token(
        subject=str(user_id),
        token_type=TOKEN_TYPE_ACCESS,
        expires_delta=timedelta(minutes=settings.JWT_ACCESS_EXPIRE_MINUTES),
        extra_claims={"role": role},
    )


def create_refresh_token(user_id: uuid.UUID | str) -> str:
    return _create_token(
        subject=str(user_id),
        token_type=TOKEN_TYPE_REFRESH,
        expires_delta=timedelta(days=settings.JWT_REFRESH_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])
    except JWTError as exc:
        raise AuthenticationError("Could not validate credentials") from exc


def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    if not token:
        raise AuthenticationError("Not authenticated")

    payload = decode_token(token)
    if payload.get("type") != TOKEN_TYPE_ACCESS:
        raise AuthenticationError("Invalid token type")

    user_id = payload.get("sub")
    if user_id is None:
        raise AuthenticationError("Invalid token payload")

    user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
    if user is None:
        raise AuthenticationError("User not found")
    if not user.is_active:
        raise AuthenticationError("User account is disabled")
    return user


def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_active:
        raise AuthenticationError("Inactive user")
    return current_user


def get_optional_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> Optional[User]:
    if not token:
        return None
    try:
        return get_current_user(token=token, db=db)
    except AuthenticationError:
        return None


def user_has_permission(user: User, permission: str) -> bool:
    role_name = user.role.name if user.role else None
    if role_name is None:
        return False
    perms = ROLE_PERMISSIONS.get(role_name, [])
    return "*" in perms or permission in perms


class require_permission:
    """FastAPI dependency factory enforcing a single RBAC permission string."""

    def __init__(self, permission: str):
        self.permission = permission

    def __call__(self, current_user: User = Depends(get_current_active_user)) -> User:
        if not user_has_permission(current_user, self.permission):
            raise AuthorizationError(
                f"Role '{current_user.role.name if current_user.role else 'unknown'}' "
                f"lacks permission '{self.permission}'"
            )
        return current_user


class require_role:
    """FastAPI dependency factory enforcing membership in an allow-list of roles."""

    def __init__(self, *roles: str):
        self.roles = set(roles)

    def __call__(self, current_user: User = Depends(get_current_active_user)) -> User:
        role_name = current_user.role.name if current_user.role else None
        if role_name not in self.roles:
            raise AuthorizationError(f"Requires one of roles: {sorted(self.roles)}")
        return current_user


require_admin = require_role("admin")


async def get_user_from_ws_token(token: str, db: Session) -> Optional[User]:
    """Resolve a User from a JWT passed as a WebSocket query parameter."""
    try:
        payload = decode_token(token)
        if payload.get("type") != TOKEN_TYPE_ACCESS:
            return None
        user_id = payload.get("sub")
        if not user_id:
            return None
        user = db.query(User).filter(User.id == uuid.UUID(user_id)).first()
        if user and user.is_active:
            return user
    except AuthenticationError:
        return None
    return None
