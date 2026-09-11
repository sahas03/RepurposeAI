"""Async (re)processing of large datasets - offloads the synchronous validation
path used on upload for cases where a dataset needs to be reprocessed later."""
import uuid

from app.core.constants import DatasetStatus, JobStatus
from app.data.loaders.dataset_loader import load_dataframe
from app.data.validation.dataset_validation import validate_dataframe
from app.models.dataset import Dataset
from app.services.job_service import update_job
from app.utils.file_utils import get_storage
from app.workers.celery_app import celery_app
from app.workers.task_utils import task_db


@celery_app.task(name="app.workers.ingestion_tasks.process_dataset_task", bind=True, max_retries=0)
def process_dataset_task(self, dataset_id: str, job_id: str | None = None) -> dict:
    dataset_uuid = uuid.UUID(dataset_id)

    if job_id:
        with task_db() as db:
            update_job(db, uuid.UUID(job_id), status=JobStatus.RUNNING, progress=10, message="Reading dataset from storage")

    try:
        with task_db() as db:
            dataset = db.get(Dataset, dataset_uuid)
            if not dataset:
                raise ValueError("Dataset no longer exists")
            storage = get_storage()
            content = storage.read(dataset.storage_path)
            df = load_dataframe(content, dataset.file_type)
            is_valid, issues, metadata = validate_dataframe(df, dataset.file_type)

            dataset.row_count = metadata["row_count"]
            dataset.column_count = metadata["column_count"]
            dataset.extra_metadata = {**dataset.extra_metadata, **metadata, "validation_issues": issues}
            dataset.status = DatasetStatus.VALID.value if is_valid else DatasetStatus.INVALID.value

            if job_id:
                update_job(db, uuid.UUID(job_id), status=JobStatus.COMPLETED, progress=100, message="Dataset processed", result=metadata)

        return {"status": "completed", "is_valid": is_valid}

    except Exception as exc:
        with task_db() as db:
            dataset = db.get(Dataset, dataset_uuid)
            if dataset:
                dataset.status = DatasetStatus.FAILED.value
            if job_id:
                update_job(db, uuid.UUID(job_id), status=JobStatus.FAILED, error=str(exc))
        return {"status": "failed", "error": str(exc)}
