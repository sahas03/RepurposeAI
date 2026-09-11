import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import ORMModel


class DiseaseOut(ORMModel):
    id: uuid.UUID
    name: str
    description: str | None
    category: str | None
    identifiers: dict[str, Any] = {}
    extra_metadata: dict[str, Any] = {}
    created_at: datetime


class DiseaseCreate(BaseModel):
    name: str
    description: str | None = None
    category: str | None = None
    identifiers: dict[str, Any] = {}
