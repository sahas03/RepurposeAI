import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import ORMModel


class GeneOut(ORMModel):
    id: uuid.UUID
    symbol: str
    name: str | None
    organism: str
    identifiers: dict[str, Any] = {}
    extra_metadata: dict[str, Any] = {}
    created_at: datetime


class GeneCreate(BaseModel):
    symbol: str
    name: str | None = None
    organism: str = "Homo sapiens"
    identifiers: dict[str, Any] = {}


class TargetOut(ORMModel):
    id: uuid.UUID
    name: str
    target_type: str
    gene_id: uuid.UUID | None
    description: str | None
    extra_metadata: dict[str, Any] = {}
    created_at: datetime


class TargetCreate(BaseModel):
    name: str
    target_type: str
    gene_id: uuid.UUID | None = None
    description: str | None = None


class InteractionOut(ORMModel):
    id: uuid.UUID
    source_entity: str
    target_entity: str
    source_type: str
    target_type: str
    interaction_type: str
    confidence_score: float
    evidence: dict[str, Any] = {}
    extra_metadata: dict[str, Any] = {}
    created_at: datetime
