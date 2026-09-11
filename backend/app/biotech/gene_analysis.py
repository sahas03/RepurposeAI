"""Gene-centric queries used by the repurposing pipeline and target/disease analyses."""
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.gene import Gene
from app.models.interaction import Interaction


def get_disease_associated_genes(db: Session, disease_id: uuid.UUID) -> list[Gene]:
    """Genes linked to a disease via a 'gene_disease' interaction edge."""
    gene_ids = db.scalars(
        select(Interaction.source_id).where(
            Interaction.interaction_type == "gene_disease",
            Interaction.target_type == "disease",
            Interaction.target_id == str(disease_id),
            Interaction.source_type == "gene",
        )
    ).all()
    if not gene_ids:
        return []
    return list(db.scalars(select(Gene).where(Gene.id.in_(gene_ids))).all())


def gene_expression_summary(values: list[float]) -> dict:
    if not values:
        return {"mean": 0.0, "std": 0.0, "min": 0.0, "max": 0.0, "count": 0}
    import numpy as np

    arr = np.array(values, dtype=float)
    return {
        "mean": round(float(arr.mean()), 4),
        "std": round(float(arr.std()), 4),
        "min": round(float(arr.min()), 4),
        "max": round(float(arr.max()), 4),
        "count": int(arr.size),
    }
