import uuid

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.types import GUID, JSONType


class Target(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "targets"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    gene_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("genes.id", ondelete="SET NULL"), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONType, default=dict, nullable=False)

    gene: Mapped["Gene | None"] = relationship("Gene", back_populates="targets")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Target {self.name}>"
