import uuid

from sqlalchemy import Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.types import GUID, JSONType


class Prediction(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "predictions"

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    experiment_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("experiments.id", ondelete="CASCADE"), nullable=True, index=True)
    drug_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("drugs.id", ondelete="CASCADE"), nullable=False, index=True)
    disease_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("diseases.id", ondelete="CASCADE"), nullable=False, index=True)
    score: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False, index=True)
    rank: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    explanation: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    features: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    model_version: Mapped[str] = mapped_column(String(50), nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="predictions")  # noqa: F821
    experiment: Mapped["Experiment | None"] = relationship("Experiment", back_populates="predictions")  # noqa: F821
    drug: Mapped["Drug"] = relationship("Drug", back_populates="predictions", lazy="joined")  # noqa: F821
    disease: Mapped["Disease"] = relationship("Disease", back_populates="predictions", lazy="joined")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Prediction drug={self.drug_id} disease={self.disease_id} score={self.score:.3f}>"
