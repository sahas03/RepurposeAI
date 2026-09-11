from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.types import JSONType


class Gene(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "genes"

    symbol: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    organism: Mapped[str] = mapped_column(String(100), default="Homo sapiens", nullable=False, index=True)
    identifiers: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONType, default=dict, nullable=False)

    targets: Mapped[list["Target"]] = relationship("Target", back_populates="gene")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Gene {self.symbol}>"
