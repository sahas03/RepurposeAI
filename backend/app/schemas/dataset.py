import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel

from app.schemas.common import ORMModel


class DatasetOut(ORMModel):
    id: uuid.UUID
    project_id: uuid.UUID
    name: str
    description: str | None
    file_name: str
    file_type: str
    file_size: int
    status: str
    row_count: int | None
    column_count: int | None
    extra_metadata: dict[str, Any] = {}
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
        populate_by_name = True


class DatasetPreviewOut(BaseModel):
    id: uuid.UUID
    columns: list[str]
    rows: list[dict[str, Any]]
    total_rows_shown: int


class DatasetMetadataOut(BaseModel):
    id: uuid.UUID
    row_count: int | None
    column_count: int | None
    columns: list[dict[str, Any]] = []
    missing_values: dict[str, int] = {}
    dtypes: dict[str, str] = {}
    basic_statistics: dict[str, Any] = {}
    quality_score: float | None = None


class DatasetValidationOut(BaseModel):
    id: uuid.UUID
    is_valid: bool
    status: str
    issues: list[str] = []
    quality_score: float | None = None
