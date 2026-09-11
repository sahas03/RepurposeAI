"""
Declarative base and shared mixins.

`base_models` imports every ORM model module so that Alembic's autogenerate
and `Base.metadata.create_all()` both see the complete schema.
"""
import uuid
from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db.types import GUID


class Base(DeclarativeBase):
    pass


class UUIDPKMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        GUID(), primary_key=True, default=uuid.uuid4, index=True
    )


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


# Import all models so they register with Base.metadata (used by Alembic env.py
# and by tests that call Base.metadata.create_all() against SQLite).
from app.models import (  # noqa: E402,F401
    user, role, project, experiment, dataset, analysis,
    compound, drug, disease, gene, target, interaction,
    prediction, recommendation, notification, audit_log, job,
    refresh_token,
)
