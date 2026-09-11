"""Gathers and scores the interaction evidence that supports a drug-disease candidate pair."""
import uuid

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.interaction import Interaction


def gather_supporting_interactions(
    db: Session, drug_id: uuid.UUID, disease_id: uuid.UUID, target_ids: list[uuid.UUID]
) -> list[dict]:
    """
    Evidence supporting a drug-disease pair is either:
      1. a direct drug_disease interaction record, or
      2. a drug_target interaction whose target is one of the drug's own targets
         that also overlaps the disease's gene associations (caller filters #2
         down to the relevant target_ids before calling this).
    """
    conditions = [
        (Interaction.interaction_type == "drug_disease")
        & (Interaction.source_type == "drug")
        & (Interaction.source_id == str(drug_id))
        & (Interaction.target_type == "disease")
        & (Interaction.target_id == str(disease_id)),
    ]
    if target_ids:
        conditions.append(
            (Interaction.interaction_type == "drug_target")
            & (Interaction.source_type == "drug")
            & (Interaction.source_id == str(drug_id))
            & (Interaction.target_type == "target")
            & (Interaction.target_id.in_([str(t) for t in target_ids]))
        )

    rows = db.scalars(select(Interaction).where(or_(*conditions))).all()
    return [
        {
            "id": str(row.id),
            "interaction_type": row.interaction_type,
            "confidence_score": row.confidence_score,
            "evidence": row.evidence,
        }
        for row in rows
    ]


def evidence_strength_label(mean_confidence: float, count: int) -> str:
    if count == 0:
        return "none"
    if mean_confidence >= 0.75 and count >= 2:
        return "strong"
    if mean_confidence >= 0.5:
        return "moderate"
    return "weak"
