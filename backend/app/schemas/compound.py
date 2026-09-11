import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import ORMModel


class CompoundOut(ORMModel):
    id: uuid.UUID
    name: str
    drug_id: uuid.UUID | None
    smiles: str | None
    molecular_formula: str | None
    molecular_weight: float | None
    properties: dict[str, Any] = {}
    extra_metadata: dict[str, Any] = {}
    created_at: datetime


class CompoundCreate(BaseModel):
    name: str
    drug_id: uuid.UUID | None = None
    smiles: str | None = None
    molecular_formula: str | None = None
    molecular_weight: float | None = None
    properties: dict[str, Any] = {}
