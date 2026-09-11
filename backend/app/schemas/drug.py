import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import ORMModel


class DrugOut(ORMModel):
    id: uuid.UUID
    name: str
    generic_name: str | None
    drug_class: str | None
    mechanism: str | None
    approval_status: str | None
    extra_metadata: dict[str, Any] = {}
    created_at: datetime


class DrugCreate(BaseModel):
    name: str
    generic_name: str | None = None
    drug_class: str | None = None
    mechanism: str | None = None
    approval_status: str | None = None
    extra_metadata: dict[str, Any] = {}
