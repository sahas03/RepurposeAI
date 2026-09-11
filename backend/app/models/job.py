import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import JobStatus, JobType
from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.types import GUID, JSONType


class Job(UUIDPKMixin, TimestampMixin, Base):
    """
    Tracks the lifecycle of any asynchronous (Celery) task so clients can poll
    REST state or subscribe to the matching /ws/jobs/{job_id} WebSocket channel.
    """

    __tablename__ = "jobs"

    task_id: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    job_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default=JobStatus.QUEUED.value, nullable=False, index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    message: Mapped[str | None] = mapped_column(String(500), nullable=True)
    result: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)

    user_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=True, index=True)
    analysis_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("analyses.id", ondelete="CASCADE"), nullable=True, index=True)
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("datasets.id", ondelete="CASCADE"), nullable=True, index=True)

    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Job {self.job_type} ({self.status})>"
