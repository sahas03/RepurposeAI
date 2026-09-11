from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.types import JSONType


class Disease(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "diseases"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    identifiers: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONType, default=dict, nullable=False)

    predictions: Mapped[list["Prediction"]] = relationship("Prediction", back_populates="disease")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Disease {self.name}>"
