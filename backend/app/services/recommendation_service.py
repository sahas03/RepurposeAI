"""
Rule-based recommendation engine.

`generate_recommendations` scans a user's recent predictions, experiments and
datasets for concrete, explainable signals (a new high-confidence candidate, a
dataset stuck in INVALID, a failed experiment, etc) and materializes each as a
Recommendation row. This is intentionally simple/rule-based rather than
another ML model - recommendations must be traceable back to the exact record
that triggered them.
"""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.constants import (
    DatasetStatus,
    ExperimentStatus,
    RecommendationPriority,
    RecommendationStatus,
    RecommendationType,
)
from app.core.exceptions import NotFoundError
from app.models.dataset import Dataset
from app.models.experiment import Experiment
from app.models.prediction import Prediction
from app.models.project import Project
from app.models.recommendation import Recommendation
from app.models.user import User
from app.schemas.common import PaginatedResponse, PaginationParams
from app.schemas.recommendation import RecommendationOut
from app.utils.pagination import paginate

HIGH_CONFIDENCE_THRESHOLD = 0.75


def list_recommendations(db: Session, user: User, params: PaginationParams, status: str | None) -> PaginatedResponse[RecommendationOut]:
    stmt = select(Recommendation).where(Recommendation.user_id == user.id)
    if status:
        stmt = stmt.where(Recommendation.status == status)
    stmt = stmt.order_by(Recommendation.created_at.desc())
    return paginate(db, stmt, params, RecommendationOut)


def generate_recommendations(db: Session, user: User, project_id: uuid.UUID | None = None) -> list[Recommendation]:
    project_filter = [Project.owner_id == user.id] if user.role.name != "admin" else []
    project_ids_stmt = select(Project.id)
    if project_id:
        project_ids_stmt = project_ids_stmt.where(Project.id == project_id)
    if project_filter:
        project_ids_stmt = project_ids_stmt.where(*project_filter)
    project_ids = list(db.scalars(project_ids_stmt).all())
    if not project_ids:
        return []

    created: list[Recommendation] = []

    high_confidence = db.scalars(
        select(Prediction)
        .where(Prediction.project_id.in_(project_ids), Prediction.confidence >= HIGH_CONFIDENCE_THRESHOLD)
        .order_by(Prediction.confidence.desc())
        .limit(5)
    ).all()
    for pred in high_confidence:
        created.append(Recommendation(
            user_id=user.id,
            project_id=pred.project_id,
            title=f"High-confidence candidate: {pred.drug.name} for {pred.disease.name}",
            description=(
                f"Computational confidence {pred.confidence:.2f} based on {pred.model_version}. "
                "Requires experimental validation before further action."
            ),
            recommendation_type=RecommendationType.HIGH_CONFIDENCE_PREDICTION.value,
            priority=RecommendationPriority.HIGH.value,
            confidence=pred.confidence,
            evidence={"prediction_id": str(pred.id), "drug_id": str(pred.drug_id), "disease_id": str(pred.disease_id)},
        ))

    invalid_datasets = db.scalars(
        select(Dataset).where(Dataset.project_id.in_(project_ids), Dataset.status.in_([DatasetStatus.INVALID.value, DatasetStatus.FAILED.value]))
    ).all()
    for ds in invalid_datasets:
        created.append(Recommendation(
            user_id=user.id,
            project_id=ds.project_id,
            title=f"Dataset needs attention: {ds.name}",
            description=f"Dataset is in status '{ds.status}' and may need to be re-uploaded or fixed.",
            recommendation_type=RecommendationType.DATASET_ATTENTION.value,
            priority=RecommendationPriority.MEDIUM.value,
            confidence=1.0,
            evidence={"dataset_id": str(ds.id), "status": ds.status},
        ))

    failed_experiments = db.scalars(
        select(Experiment).where(Experiment.project_id.in_(project_ids), Experiment.status == ExperimentStatus.FAILED.value)
    ).all()
    for exp in failed_experiments:
        created.append(Recommendation(
            user_id=user.id,
            project_id=exp.project_id,
            title=f"Experiment failed: {exp.name}",
            description="Review the experiment parameters and input data, then retry.",
            recommendation_type=RecommendationType.FAILED_EXPERIMENT.value,
            priority=RecommendationPriority.MEDIUM.value,
            confidence=1.0,
            evidence={"experiment_id": str(exp.id)},
        ))

    # De-duplicate against already-active recommendations referencing the same evidence.
    existing_evidence_keys = {
        _evidence_key(r.recommendation_type, r.evidence)
        for r in db.scalars(select(Recommendation).where(Recommendation.user_id == user.id, Recommendation.status == RecommendationStatus.ACTIVE.value)).all()
    }
    to_add = [r for r in created if _evidence_key(r.recommendation_type, r.evidence) not in existing_evidence_keys]

    db.add_all(to_add)
    db.flush()
    for r in to_add:
        db.refresh(r)
    return to_add


def _evidence_key(rec_type: str, evidence: dict) -> str:
    return f"{rec_type}:{sorted(evidence.items())}"


def update_recommendation(db: Session, user: User, recommendation_id: uuid.UUID, status: str | None, priority: str | None) -> Recommendation:
    rec = db.get(Recommendation, recommendation_id)
    if not rec or rec.user_id != user.id:
        raise NotFoundError("Recommendation was not found", code="RECOMMENDATION_NOT_FOUND")
    if status:
        rec.status = status
    if priority:
        rec.priority = priority
    db.flush()
    db.refresh(rec)
    return rec


def dismiss_recommendation(db: Session, user: User, recommendation_id: uuid.UUID) -> Recommendation:
    return update_recommendation(db, user, recommendation_id, status=RecommendationStatus.DISMISSED.value, priority=None)
