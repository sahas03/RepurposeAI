import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import ORMModel
from app.schemas.drug import DrugOut
from app.schemas.disease import DiseaseOut


class RepurposingRunRequest(BaseModel):
    disease_id: uuid.UUID
    dataset_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    experiment_id: uuid.UUID | None = None
    parameters: dict[str, Any] = {}


class RepurposingRunResponse(BaseModel):
    job_id: uuid.UUID
    status: str


class PredictionOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    experiment_id: uuid.UUID | None
    drug: DrugOut
    disease: DiseaseOut
    score: float
    confidence: float
    rank: int | None
    explanation: dict[str, Any]
    features: dict[str, Any]
    model_version: str
    created_at: datetime


class RepurposingResultsOut(BaseModel):
    job_id: uuid.UUID
    status: str
    disease_id: uuid.UUID | None = None
    predictions: list[PredictionOut] = []
