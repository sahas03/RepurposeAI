import uuid

from sqlalchemy import BigInteger, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.constants import DatasetStatus
from app.db.base import Base, TimestampMixin, UUIDPKMixin
from app.db.types import GUID, JSONType


class Dataset(UUIDPKMixin, TimestampMixin, Base):
    __tablename__ = "datasets"

    project_id: Mapped[uuid.UUID] = mapped_column(GUID(), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_name: Mapped[str] = mapped_column(String(500), nullable=False)
    file_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    file_size: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    storage_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    status: Mapped[str] = mapped_column(String(30), default=DatasetStatus.UPLOADED.value, nullable=False, index=True)
    row_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    column_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONType, default=dict, nullable=False)

    project: Mapped["Project"] = relationship("Project", back_populates="datasets")  # noqa: F821
    analyses: Mapped[list["Analysis"]] = relationship("Analysis", back_populates="dataset")  # noqa: F821

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Dataset {self.name} ({self.status})>"
