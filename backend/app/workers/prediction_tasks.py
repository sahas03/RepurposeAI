"""Celery task backing POST /api/v1/repurposing/run."""
import uuid
from datetime import datetime, timezone

from app.biotech.drug_repurposing import run_repurposing_analysis
from app.core.constants import JobStatus, NotificationType
from app.models.prediction import Prediction
from app.services.job_service import update_job
from app.services.notification_service import create_notification
from app.workers.celery_app import celery_app
from app.workers.task_utils import task_db


@celery_app.task(name="app.workers.prediction_tasks.run_repurposing_task", bind=True, max_retries=0)
def run_repurposing_task(
    self,
    job_id: str,
    disease_id: str,
    user_id: str,
    project_id: str | None,
    experiment_id: str | None,
    parameters: dict,
) -> dict:
    job_uuid = uuid.UUID(job_id)
    top_k = int((parameters or {}).get("top_k", 20))

    with task_db() as db:
        update_job(db, job_uuid, status=JobStatus.RUNNING, progress=10, message="Validating disease and gathering evidence")

    try:
        with task_db() as db:
            result = run_repurposing_analysis(db, uuid.UUID(disease_id), top_k=top_k)

        with task_db() as db:
            update_job(db, job_uuid, status=JobStatus.RUNNING, progress=60, message="Scoring and ranking candidates")

            prediction_ids = []
            high_confidence_found = False
            for item in result["results"]:
                prediction = Prediction(
                    project_id=uuid.UUID(project_id) if project_id else _get_or_create_default_project(db, user_id),
                    experiment_id=uuid.UUID(experiment_id) if experiment_id else None,
                    drug_id=uuid.UUID(item["drug_id"]),
                    disease_id=uuid.UUID(disease_id),
                    score=item["score"],
                    confidence=item["confidence"],
                    rank=item["rank"],
                    explanation=item["explanation"],
                    features=item["features"],
                    model_version=item["model_version"],
                )
                db.add(prediction)
                db.flush()
                prediction_ids.append(str(prediction.id))
                if item["confidence"] >= 0.75:
                    high_confidence_found = True

            job_result = {
                "disease_id": disease_id,
                "disease_name": result["disease_name"],
                "candidate_pool_size": result["candidate_pool_size"],
                "prediction_ids": prediction_ids,
            }
            update_job(db, job_uuid, status=JobStatus.COMPLETED, progress=100, message="Repurposing run completed", result=job_result)

            if high_confidence_found:
                create_notification(
                    db, uuid.UUID(user_id), "High-confidence repurposing candidate found",
                    f"A high-confidence drug repurposing candidate was found for '{result['disease_name']}'.",
                    NotificationType.HIGH_CONFIDENCE_CANDIDATE,
                    {"job_id": job_id, "disease_id": disease_id},
                )
            create_notification(
                db, uuid.UUID(user_id), "Repurposing run completed",
                f"Found {len(prediction_ids)} candidate(s) for '{result['disease_name']}'.",
                NotificationType.PREDICTION_GENERATED,
                {"job_id": job_id},
            )

        return job_result

    except Exception as exc:
        with task_db() as db:
            update_job(db, job_uuid, status=JobStatus.FAILED, error=str(exc), message="Repurposing run failed")
        return {"status": "failed", "error": str(exc)}


def _get_or_create_default_project(db, user_id: str):
    """Predictions require a project_id; fall back to (or create) the user's default scratch project."""
    from app.models.project import Project

    user_uuid = uuid.UUID(user_id)
    project = db.query(Project).filter(Project.owner_id == user_uuid, Project.name == "Default Repurposing Workspace").first()
    if project:
        return project.id
    project = Project(owner_id=user_uuid, name="Default Repurposing Workspace", description="Auto-created for ad-hoc repurposing runs.")
    db.add(project)
    db.flush()
    return project.id
