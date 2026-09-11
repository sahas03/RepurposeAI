from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.types import JSONType


class Interaction(UUIDPKMixin, TimestampMixin, Base):
    """
    A generic, typed edge between two biotech entities (drug-target, gene-disease,
    drug-gene, etc). `source_entity`/`target_entity` are human-readable labels
    (e.g. "drug:Metformin"); `source_type`/`source_id` and `target_type`/`target_id`
    are the machine-queryable references used for joins and filtering.
    """

    __tablename__ = "interactions"

    source_entity: Mapped[str] = mapped_column(String(500), nullable=False)
    target_entity: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    target_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    interaction_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    confidence_score: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    evidence: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONType, default=dict, nullable=False)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Interaction {self.source_entity} -> {self.target_entity} ({self.interaction_type})>"
