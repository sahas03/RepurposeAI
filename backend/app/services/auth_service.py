import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.constants import AuditAction, RoleName
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError, ValidationAppError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.refresh_token import RefreshToken
from app.models.role import Role
from app.models.user import User
from app.services.audit_service import log_action


def get_or_create_role(db: Session, name: str) -> Role:
    role = db.scalar(select(Role).where(Role.name == name))
    if role:
        return role
    role = Role(name=name, permissions=[])
    db.add(role)
    db.flush()
    return role


def register_user(db: Session, name: str, email: str, password: str, role_name: str = RoleName.VIEWER.value) -> User:
    if role_name not in {r.value for r in RoleName}:
        raise ValidationAppError(f"Invalid role '{role_name}'", code="INVALID_ROLE")

    existing = db.scalar(select(User).where(User.email == email.lower()))
    if existing:
        raise ConflictError("An account with this email already exists", code="EMAIL_TAKEN")

    role = get_or_create_role(db, role_name)
    user = User(
        name=name,
        email=email.lower(),
        password_hash=hash_password(password),
        role_id=role.id,
        is_active=True,
    )
    db.add(user)
    db.flush()
    db.refresh(user)
    log_action(db, user.id, AuditAction.REGISTER, "user", str(user.id))
    return user


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email.lower()))
    if not user or not verify_password(password, user.password_hash):
        raise AuthenticationError("Invalid email or password", code="INVALID_CREDENTIALS")
    if not user.is_active:
        raise AuthenticationError("This account has been disabled", code="ACCOUNT_DISABLED")
    return user


def issue_tokens(db: Session, user: User) -> dict:
    user.last_login = datetime.now(timezone.utc)
    access_token = create_access_token(user.id, user.role.name)
    refresh_token = create_refresh_token(user.id)

    payload = decode_token(refresh_token)
    db.add(RefreshToken(
        user_id=user.id,
        token_jti=payload["jti"],
        expires_at=datetime.fromtimestamp(payload["exp"], tz=timezone.utc),
        created_at=datetime.now(timezone.utc),
    ))
    db.flush()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "expires_in": settings.JWT_ACCESS_EXPIRE_MINUTES * 60,
    }


def login(db: Session, email: str, password: str) -> tuple[User, dict]:
    user = authenticate_user(db, email, password)
    tokens = issue_tokens(db, user)
    log_action(db, user.id, AuditAction.LOGIN, "user", str(user.id))
    return user, tokens


def refresh_access_token(db: Session, refresh_token: str) -> dict:
    payload = decode_token(refresh_token)
    if payload.get("type") != "refresh":
        raise AuthenticationError("Invalid token type", code="INVALID_TOKEN_TYPE")

    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_jti == payload["jti"]))
    if not stored or stored.revoked:
        raise AuthenticationError("Refresh token has been revoked", code="TOKEN_REVOKED")
    expires_at = stored.expires_at
    if expires_at.tzinfo is None:
        # SQLite (used in tests) does not preserve tzinfo on DateTime(timezone=True) columns;
        # PostgreSQL does. Normalize to UTC so this comparison is correct on both.
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at < datetime.now(timezone.utc):
        raise AuthenticationError("Refresh token has expired", code="TOKEN_EXPIRED")

    user = db.get(User, uuid.UUID(payload["sub"]))
    if not user or not user.is_active:
        raise AuthenticationError("User not found or inactive", code="USER_INACTIVE")

    # Rotate: revoke the old refresh token and issue a fresh pair.
    stored.revoked = True
    tokens = issue_tokens(db, user)
    return tokens


def logout(db: Session, user: User, refresh_token: str | None) -> None:
    if refresh_token:
        try:
            payload = decode_token(refresh_token)
            stored = db.scalar(select(RefreshToken).where(RefreshToken.token_jti == payload.get("jti")))
            if stored:
                stored.revoked = True
        except AuthenticationError:
            pass
    else:
        db.query(RefreshToken).filter(RefreshToken.user_id == user.id, RefreshToken.revoked.is_(False)).update({"revoked": True})
    log_action(db, user.id, AuditAction.LOGOUT, "user", str(user.id))


def update_me(db: Session, user: User, name: str | None, password: str | None) -> User:
    if name:
        user.name = name
    if password:
        user.password_hash = hash_password(password)
    db.flush()
    db.refresh(user)
    log_action(db, user.id, AuditAction.USER_UPDATE, "user", str(user.id))
    return user
