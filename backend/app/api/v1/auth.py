from fastapi import APIRouter, Body, Depends, status
from sqlalchemy.orm import Session

from app.core.security import get_current_active_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UpdateMeRequest,
    UserOut,
)
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", status_code=status.HTTP_201_CREATED, summary="Register a new user")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    user = auth_service.register_user(db, payload.name, payload.email, payload.password, payload.role)
    db.commit()
    return {"success": True, "data": UserOut.model_validate(user)}


@router.post("/login", summary="Authenticate and receive access/refresh tokens")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user, tokens = auth_service.login(db, payload.email, payload.password)
    db.commit()
    return {"success": True, "data": TokenResponse(**tokens)}


@router.post("/refresh", summary="Exchange a refresh token for a new token pair")
def refresh(payload: RefreshRequest, db: Session = Depends(get_db)):
    tokens = auth_service.refresh_access_token(db, payload.refresh_token)
    db.commit()
    return {"success": True, "data": TokenResponse(**tokens)}


@router.post("/logout", summary="Revoke the current session's refresh token(s)")
def logout(payload: RefreshRequest | None = Body(default=None), db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    auth_service.logout(db, current_user, payload.refresh_token if payload else None)
    db.commit()
    return {"success": True, "data": {"message": "Logged out"}}


@router.get("/me", summary="Get the current authenticated user")
def get_me(current_user: User = Depends(get_current_active_user)):
    return {"success": True, "data": UserOut.model_validate(current_user)}


@router.put("/me", summary="Update the current user's name and/or password")
def update_me(payload: UpdateMeRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_active_user)):
    user = auth_service.update_me(db, current_user, payload.name, payload.password)
    db.commit()
    return {"success": True, "data": UserOut.model_validate(user)}
