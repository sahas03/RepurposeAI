import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.constants import AnalysisType
from app.schemas.common import ORMModel


class AnalysisRunRequest(BaseModel):
    experiment_id: uuid.UUID
    dataset_id: uuid.UUID | None = None
    analysis_type: AnalysisType
    parameters: dict[str, Any] = Field(default_factory=dict)


class AnalysisOut(ORMModel):
    id: uuid.UUID
    experiment_id: uuid.UUID
    dataset_id: uuid.UUID | None
    analysis_type: str
    status: str
    progress: int
    parameters: dict[str, Any]
    results: dict[str, Any] | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime


class AnalysisRunResponse(BaseModel):
    job_id: uuid.UUID
    analysis_id: uuid.UUID
    status: str
