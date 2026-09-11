import uuid

from sqlalchemy import Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import RecommendationPriority, RecommendationStatus
from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.types import GUID, JSONType


class Recommendation(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "recommendations"

    user_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendation_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    priority: Mapped[str] = mapped_column(String(20), default=RecommendationPriority.MEDIUM.value, nullable=False, index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=RecommendationStatus.ACTIVE.value, nullable=False, index=True)

    user: Mapped["User"] = relationship("User", back_populates="recommendations")  # noqa: F821
    project: Mapped["Project | None"] = relationship("Project", back_populates="recommendations")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Recommendation {self.title}>"
