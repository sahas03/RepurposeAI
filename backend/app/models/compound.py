import uuid

from sqlalchemy import Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.types import GUID, JSONType


class Compound(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "compounds"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    drug_id: Mapped[uuid.UUID | None] = mapped_column(GUID(), ForeignKey("drugs.id", ondelete="SET NULL"), nullable=True, index=True)
    smiles: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    molecular_formula: Mapped[str | None] = mapped_column(String(255), nullable=True)
    molecular_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    properties: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONType, default=dict, nullable=False)

    drug: Mapped["Drug | None"] = relationship("Drug", back_populates="compounds")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Compound {self.name}>"
