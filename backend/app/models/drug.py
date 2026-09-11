from sqlalchemy import String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.types import JSONType


class Drug(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "drugs"

    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    generic_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    drug_class: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    mechanism: Mapped[str | None] = mapped_column(Text, nullable=True)
    approval_status: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONType, default=dict, nullable=False)

    compounds: Mapped[list["Compound"]] = relationship("Compound", back_populates="drug")  # noqa: F821
    predictions: Mapped[list["Prediction"]] = relationship("Prediction", back_populates="drug")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Drug {self.name}>"
