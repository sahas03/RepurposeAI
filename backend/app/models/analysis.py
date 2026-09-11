import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import AnalysisType, JobStatus
from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.types import GUID, JSONType


class Analysis(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "analyses"

    experiment_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True)
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("datasets.id", ondelete="SET NULL"), nullable=True, index=True)
    analysis_type: Mapped[str] = mapped_column(String(50), default=AnalysisType.STATISTICAL_ANALYSIS.value, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(30), default=JobStatus.QUEUED.value, nullable=False, index=True)
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    parameters: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    results: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    experiment: Mapped["Experiment"] = relationship("Experiment", back_populates="analyses")  # noqa: F821
    dataset: Mapped["Dataset | None"] = relationship("Dataset", back_populates="analyses")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Analysis {self.analysis_type} ({self.status})>"
