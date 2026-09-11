import uuid

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.core.security import require_permission
from app.db.session import get_db
from app.models.user import User
from app.schemas.common import PaginationParams
from app.schemas.dataset import (
    DatasetMetadataOut,
    DatasetOut,
    DatasetPreviewOut,
    DatasetValidationOut,
)
from app.services import dataset_service

router = APIRouter(prefix="/datasets", tags=["Datasets"])


@router.get("", summary="List datasets")
def list_datasets(
    page: int = 1, page_size: int = 20, project_id: uuid.UUID | None = None,
    status: str | None = None, search: str | None = None,
    db: Session = Depends(get_db), current_user: User = Depends(require_permission("dataset:read")),
):
    params = PaginationParams(page=page, page_size=page_size)
    result = dataset_service.list_datasets(db, current_user, params, project_id, status, search)
    return {"success": True, "data": result}


@router.post("/upload", status_code=201, summary="Upload a dataset file (CSV, JSON, XLSX, FASTA, FASTQ)")
async def upload_dataset(
    project_id: uuid.UUID = Form(...),
    name: str | None = Form(default=None),
    description: str | None = Form(default=None),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("dataset:write")),
):
    content = await file.read()
    dataset = dataset_service.upload_dataset(db, current_user, project_id, name or file.filename, description, file.filename, content)
    db.commit()
    return {"success": True, "data": DatasetOut.model_validate(dataset)}


@router.get("/{dataset_id}", summary="Get a dataset by id")
def get_dataset(dataset_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("dataset:read"))):
    dataset = dataset_service.get_dataset_or_404(db, dataset_id)
    dataset_service.check_dataset_access(db, current_user, dataset)
    return {"success": True, "data": DatasetOut.model_validate(dataset)}


@router.delete("/{dataset_id}", summary="Delete a dataset and its stored file")
def delete_dataset(dataset_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("dataset:delete"))):
    dataset_service.delete_dataset(db, current_user, dataset_id)
    db.commit()
    return {"success": True, "data": {"message": "Dataset deleted"}}


@router.get("/{dataset_id}/preview", summary="Preview the first rows of a dataset")
def preview_dataset(dataset_id: uuid.UUID, limit: int = 50, db: Session = Depends(get_db), current_user: User = Depends(require_permission("dataset:read"))):
    data = dataset_service.preview_dataset(db, current_user, dataset_id, limit)
    return {"success": True, "data": DatasetPreviewOut(**data)}


@router.get("/{dataset_id}/metadata", summary="Get computed statistics/metadata for a dataset")
def get_dataset_metadata(dataset_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("dataset:read"))):
    data = dataset_service.dataset_metadata(db, current_user, dataset_id)
    return {"success": True, "data": DatasetMetadataOut(**data)}


@router.post("/{dataset_id}/validate", summary="Re-run structural validation on a dataset")
def validate_dataset(dataset_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(require_permission("dataset:write"))):
    dataset = dataset_service.revalidate_dataset(db, current_user, dataset_id)
    db.commit()
    meta = dataset.extra_metadata or {}
    return {"success": True, "data": DatasetValidationOut(
        id=dataset.id, is_valid=dataset.status == "VALID", status=dataset.status,
        issues=meta.get("validation_issues", []), quality_score=meta.get("quality_score"),
    )}
