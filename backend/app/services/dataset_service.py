import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.constants import AuditAction, DatasetStatus
from app.core.exceptions import NotFoundError
from app.data.loaders.dataset_loader import load_dataframe
from app.data.validation.dataset_validation import validate_dataframe
from app.models.dataset import Dataset
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.dataset import DatasetOut
from app.services.audit_service import log_action
from app.services.project_service import ensure_project_access, get_project_or_404
from app.utils.file_utils import build_dataset_storage_key, get_storage
from app.utils.pagination import paginate
from app.utils.validators import validate_upload_file


def get_dataset_or_404(db: Session, dataset_id: uuid.UUID) -> Dataset:
    dataset = db.get(Dataset, dataset_id)
    if not dataset:
        raise NotFoundError("Dataset was not found", code="DATASET_NOT_FOUND")
    return dataset


def check_dataset_access(db: Session, user: User, dataset: Dataset) -> None:
    project = get_project_or_404(db, dataset.project_id)
    ensure_project_access(project, user)


def list_datasets(db: Session, user: User, params: PaginationParams, project_id: uuid.UUID | None, status: str | None, search: str | None) -> PaginatedResponse[DatasetOut]:
    stmt = select(Dataset)
    if user.role.name != "admin":
        from app.models.project import Project
        stmt = stmt.join(Project, Project.id == Dataset.project_id).where(Project.owner_id == user.id)
    if project_id:
        stmt = stmt.where(Dataset.project_id == project_id)
    if status:
        stmt = stmt.where(Dataset.status == status)
    if search:
        stmt = stmt.where(or_(Dataset.name.ilike(f"%{search}%"), Dataset.file_name.ilike(f"%{search}%")))
    stmt = stmt.order_by(Dataset.created_at.desc())
    return paginate(db, stmt, params, DatasetOut)


def upload_dataset(db: Session, user: User, project_id: uuid.UUID, name: str, description: str | None, file_name: str, content: bytes) -> Dataset:
    project = get_project_or_404(db, project_id)
    ensure_project_access(project, user)

    file_ext = validate_upload_file(file_name, len(content))

    dataset = Dataset(
        project_id=project_id,
        name=name or file_name,
        description=description,
        file_name=file_name,
        file_type=file_ext,
        file_size=len(content),
        storage_path="",
        status=DatasetStatus.UPLOADED.value,
    )
    db.add(dataset)
    db.flush()

    storage = get_storage()
    storage_key = build_dataset_storage_key(str(project_id), str(dataset.id), file_name)
    storage.save(content, storage_key)
    dataset.storage_path = storage_key
    dataset.status = DatasetStatus.VALIDATING.value
    db.flush()
    db.refresh(dataset)

    log_action(db, user.id, AuditAction.DATASET_UPLOAD, "dataset", str(dataset.id), {"file_name": file_name, "size": len(content)})

    _run_validation(db, dataset)
    db.refresh(dataset)
    return dataset


def _run_validation(db: Session, dataset: Dataset) -> None:
    """Synchronous validation pass run right after upload (also re-runnable via /validate)."""
    try:
        storage = get_storage()
        content = storage.read(dataset.storage_path)
        df = load_dataframe(content, dataset.file_type)
        is_valid, issues, metadata = validate_dataframe(df, dataset.file_type)

        dataset.row_count = metadata["row_count"]
        dataset.column_count = metadata["column_count"]
        dataset.extra_metadata = {**dataset.extra_metadata, **metadata, "validation_issues": issues}
        dataset.status = DatasetStatus.VALID.value if is_valid else DatasetStatus.INVALID.value
        db.flush()

        if not is_valid:
            from app.core.constants import NotificationType
            from app.services.notification_service import create_notification
            from app.models.project import Project

            project = db.get(Project, dataset.project_id)
            create_notification(
                db, project.owner_id,
                title="Dataset validation failed",
                message=f"Dataset '{dataset.name}' failed validation: {'; '.join(issues[:3])}",
                notification_type=NotificationType.DATASET_VALIDATION_FAILED,
                metadata={"dataset_id": str(dataset.id)},
            )
    except Exception as exc:
        dataset.status = DatasetStatus.FAILED.value
        dataset.extra_metadata = {**dataset.extra_metadata, "validation_error": str(exc)}
        db.flush()


def revalidate_dataset(db: Session, user: User, dataset_id: uuid.UUID) -> Dataset:
    dataset = get_dataset_or_404(db, dataset_id)
    check_dataset_access(db, user, dataset)
    dataset.status = DatasetStatus.VALIDATING.value
    db.flush()
    _run_validation(db, dataset)
    db.refresh(dataset)
    return dataset


def delete_dataset(db: Session, user: User, dataset_id: uuid.UUID) -> None:
    dataset = get_dataset_or_404(db, dataset_id)
    check_dataset_access(db, user, dataset)
    storage = get_storage()
    try:
        storage.delete(dataset.storage_path)
    except Exception:
        pass
    db.delete(dataset)
    db.flush()
    log_action(db, user.id, AuditAction.DATASET_DELETE, "dataset", str(dataset_id))


def preview_dataset(db: Session, user: User, dataset_id: uuid.UUID, limit: int = 50) -> dict:
    dataset = get_dataset_or_404(db, dataset_id)
    check_dataset_access(db, user, dataset)
    storage = get_storage()
    content = storage.read(dataset.storage_path)
    df = load_dataframe(content, dataset.file_type)
    preview_df = df.head(limit).fillna("")
    return {
        "id": dataset.id,
        "columns": [str(c) for c in df.columns],
        "rows": preview_df.to_dict(orient="records"),
        "total_rows_shown": len(preview_df),
    }


def dataset_metadata(db: Session, user: User, dataset_id: uuid.UUID) -> dict:
    dataset = get_dataset_or_404(db, dataset_id)
    check_dataset_access(db, user, dataset)
    meta = dataset.extra_metadata or {}
    return {
        "id": dataset.id,
        "row_count": dataset.row_count,
        "column_count": dataset.column_count,
        "columns": meta.get("columns", []),
        "missing_values": meta.get("missing_values", {}),
        "dtypes": meta.get("dtypes", {}),
        "basic_statistics": meta.get("basic_statistics", {}),
        "quality_score": meta.get("quality_score"),
    }
