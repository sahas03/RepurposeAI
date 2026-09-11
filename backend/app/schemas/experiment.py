import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.core.constants import ExperimentStatus, ExperimentType
from app.schemas.common import ORMModel


class ExperimentCreate(BaseModel):
    project_id: uuid.UUID
    name: str = Field(min_length=1, max_length=255)
    description: str | None = None
    experiment_type: ExperimentType = ExperimentType.CUSTOM
    parameters: dict[str, Any] = Field(default_factory=dict)


class ExperimentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    parameters: dict[str, Any] | None = None
    status: ExperimentStatus | None = None


class ExperimentOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None
    experiment_type: str
    status: str
    progress: int
    parameters: dict[str, Any]
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime


class ExperimentStatusOut(ORMModel):
    id: uuid.UUID
    status: str
    progress: int
    started_at: datetime | None
    completed_at: datetime | None


class ExperimentResultsOut(BaseModel):
    id: uuid.UUID
    status: str
    analyses: list[dict[str, Any]]
    predictions: list[dict[str, Any]]
