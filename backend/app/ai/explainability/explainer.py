"""
Human-readable explanations for a prediction.

Output always distinguishes computational prediction from the underlying
evidence tiers, and never claims clinical efficacy - see app/core/constants.py
EvidenceLevel and PART 37 of the product spec ("scientific safety").
"""
from app.core.constants import EvidenceLevel
from app.ai.feature_engineering.feature_engineering import RepurposingFeatures


def generate_explanation(
    drug_name: str,
    disease_name: str,
    features: RepurposingFeatures,
    score: float,
    confidence: float,
    model_name: str,
    model_version: str,
) -> dict:
    reasons: list[str] = []

    if features.gene_overlap_count > 0:
        reasons.append(
            f"{drug_name}'s known targets overlap with {features.gene_overlap_count} "
            f"gene(s) associated with {disease_name} "
            f"({features.gene_overlap_ratio:.0%} of the disease's associated genes)."
        )
    else:
        reasons.append(
            f"No direct gene-target overlap was found between {drug_name} and {disease_name}; "
            "this candidate relies on other evidence signals."
        )

    if features.evidence_count > 0:
        reasons.append(
            f"{features.evidence_count} supporting interaction record(s) were found "
            f"with an average confidence of {features.evidence_mean_confidence:.2f}."
        )

    if features.compound_similarity_score > 0.3:
        reasons.append(
            f"Structural/property similarity to compounds already implicated in this "
            f"disease area scored {features.compound_similarity_score:.2f} (0-1 scale)."
        )

    if features.target_count > 0:
        reasons.append(f"{drug_name} has {features.target_count} characterized target(s) in the platform's data.")

    reasons.append(
        "This is a computational prediction requiring experimental validation before any "
        "biological or clinical conclusion is drawn."
    )

    supporting_evidence = [
        {
            "type": EvidenceLevel.COMPUTATIONAL_PREDICTION.value,
            "description": f"Model-derived score {score:.3f} with confidence {confidence:.3f}.",
        },
        {
            "type": EvidenceLevel.SUPPORTING_EVIDENCE.value,
            "description": f"{features.evidence_count} database interaction record(s) referenced.",
        },
    ]

    return {
        "prediction": f"{drug_name} is a computationally predicted repurposing candidate for {disease_name}.",
        "confidence": round(confidence, 4),
        "score": round(score, 4),
        "reasons": reasons,
        "supporting_evidence": supporting_evidence,
        "evidence_levels_used": [EvidenceLevel.COMPUTATIONAL_PREDICTION.value, EvidenceLevel.SUPPORTING_EVIDENCE.value],
        "model_name": model_name,
        "model_version": model_version,
        "disclaimer": (
            "Computational prediction only. Not a clinical or diagnostic claim. "
            "Requires experimental and/or clinical validation."
        ),
    }
