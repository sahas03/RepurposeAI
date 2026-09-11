import uuid
from datetime import datetime
from typing import Any

from app.schemas.common import ORMModel


class JobOut(ORMModel):
    id: uuid.UUID
    task_id: str | None
    job_type: str
    status: str
    progress: int
    message: str | None
    result: dict[str, Any] | None
    error: str | None
    started_at: datetime | None
    completed_at: datetime | None
    created_at: datetime
