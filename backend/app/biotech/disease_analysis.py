"""Disease-centric summary used by the /diseases/{id} detail view and repurposing input validation."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.biotech.gene_analysis import get_disease_associated_genes
from app.core.exceptions import NotFoundError
from app.models.disease import Disease
from app.models.prediction import Prediction


def get_disease_or_404(db: Session, disease_id: uuid.UUID) -> Disease:
    disease = db.get(Disease, disease_id)
    if not disease:
        raise NotFoundError("Disease was not found", code="DISEASE_NOT_FOUND")
    return disease


def disease_profile(db: Session, disease_id: uuid.UUID) -> dict:
    disease = get_disease_or_404(db, disease_id)
    genes = get_disease_associated_genes(db, disease_id)
    prediction_count = db.scalar(
        select(Prediction).where(Prediction.disease_id == disease_id).limit(1)
    )
    top_predictions = db.scalars(
        select(Prediction)
        .where(Prediction.disease_id == disease_id)
        .order_by(Prediction.score.desc())
        .limit(5)
    ).all()
    return {
        "disease": disease,
        "associated_gene_count": len(genes),
        "associated_genes": [g.symbol for g in genes],
        "has_predictions": prediction_count is not None,
        "top_predictions": top_predictions,
    }
