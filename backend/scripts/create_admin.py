#!/usr/bin/env python
"""
Creates (or promotes) an admin user.

Usage:
    python scripts/create_admin.py [--email EMAIL] [--password PASSWORD] [--name NAME]

Defaults to the FIRST_SUPERUSER_* values in settings/.env if flags are omitted.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.constants import RoleName  # noqa: E402
from app.core.security import hash_password  # noqa: E402
from app.db.database import SessionLocal  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.auth_service import get_or_create_role  # noqa: E402


def create_admin(email: str, password: str, name: str) -> None:
    db = SessionLocal()
    try:
        role = get_or_create_role(db, RoleName.ADMIN.value)
        existing = db.scalar(select(User).where(User.email == email.lower()))
        if existing:
            existing.role_id = role.id
            existing.is_active = True
            existing.password_hash = hash_password(password)
            db.commit()
            print(f"Existing user '{email}' promoted to admin and password reset.")
            return

        user = User(name=name, email=email.lower(), password_hash=hash_password(password), role_id=role.id, is_active=True)
        db.add(user)
        db.commit()
        print(f"Admin user created: {email}")
    finally:
        db.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Create or promote an admin user.")
    parser.add_argument("--email", default=settings.FIRST_SUPERUSER_EMAIL)
    parser.add_argument("--password", default=settings.FIRST_SUPERUSER_PASSWORD)
    parser.add_argument("--name", default=settings.FIRST_SUPERUSER_NAME)
    args = parser.parse_args()
    create_admin(args.email, args.password, args.name)
