import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import ORMModel


class RecommendationOut(ORMModel):
    id: uuid.UUID
    user_id: uuid.UUID
    project_id: uuid.UUID | None
    title: str
    description: str | None
    recommendation_type: str
    priority: str
    confidence: float
    evidence: dict[str, Any] = {}
    status: str
    created_at: datetime


class RecommendationUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None


class RecommendationGenerateRequest(BaseModel):
    project_id: uuid.UUID | None = None
