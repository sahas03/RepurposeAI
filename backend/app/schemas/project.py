import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.core.constants import ProjectStatus
from app.schemas.common import ORMModel


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: ProjectStatus | None = None


class ProjectOut(ORMModel):
    id: uuid.UUID
    owner_id: uuid.UUID
    name: str
    description: str | None
    status: str
    created_at: datetime
    updated_at: datetime


class ProjectSummary(BaseModel):
    project: ProjectOut
    experiment_count: int
    dataset_count: int
    analysis_count: int
    prediction_count: int
    completed_experiments: int
    running_experiments: int
    failed_experiments: int
    high_confidence_predictions: int
