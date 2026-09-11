from datetime import datetime
from typing import Any

from pydantic import BaseModel


class DashboardOverview(BaseModel):
    total_projects: int
    active_projects: int
    total_experiments: int
    running_experiments: int
    completed_experiments: int
    failed_experiments: int
    total_datasets: int
    analyses_running: int
    predictions_generated: int
    high_confidence_candidates: int


class ActivityItem(BaseModel):
    type: str
    title: str
    description: str
    timestamp: datetime
    resource_id: str | None = None


class SystemStatus(BaseModel):
    database: str
    redis: str
    celery_workers: int
    environment: str
    version: str
    uptime_seconds: float


class DashboardMetrics(BaseModel):
    predictions_by_confidence: dict[str, int]
    experiments_by_status: dict[str, int]
    datasets_by_status: dict[str, int]
    analyses_by_type: dict[str, int]


class AnalyticsSeries(BaseModel):
    range: str
    labels: list[str]
    series: dict[str, list[float]]
    summary: dict[str, Any] = {}
