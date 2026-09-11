"""
Feature engineering for the drug repurposing pipeline.

Every function here is pure (no DB access) so it can be unit-tested and reused
between the online pipeline and offline model training.
"""
from dataclasses import dataclass, field


@dataclass
class RepurposingFeatures:
    gene_overlap_count: int
    gene_overlap_ratio: float
    target_count: int
    evidence_count: int
    evidence_mean_confidence: float
    compound_similarity_score: float
    known_target_interaction_score: float

    def to_vector(self) -> list[float]:
        return [
            self.gene_overlap_count,
            self.gene_overlap_ratio,
            self.target_count,
            self.evidence_count,
            self.evidence_mean_confidence,
            self.compound_similarity_score,
            self.known_target_interaction_score,
        ]

    def to_dict(self) -> dict:
        return {
            "gene_overlap_count": self.gene_overlap_count,
            "gene_overlap_ratio": round(self.gene_overlap_ratio, 4),
            "target_count": self.target_count,
            "evidence_count": self.evidence_count,
            "evidence_mean_confidence": round(self.evidence_mean_confidence, 4),
            "compound_similarity_score": round(self.compound_similarity_score, 4),
            "known_target_interaction_score": round(self.known_target_interaction_score, 4),
        }

    @staticmethod
    def feature_names() -> list[str]:
        return [
            "gene_overlap_count", "gene_overlap_ratio", "target_count",
            "evidence_count", "evidence_mean_confidence",
            "compound_similarity_score", "known_target_interaction_score",
        ]


def build_repurposing_features(
    disease_gene_ids: set[str],
    drug_target_gene_ids: set[str],
    target_count: int,
    supporting_interactions: list[dict],
    compound_similarity_score: float,
) -> RepurposingFeatures:
    overlap = disease_gene_ids & drug_target_gene_ids
    gene_overlap_count = len(overlap)
    gene_overlap_ratio = gene_overlap_count / len(disease_gene_ids) if disease_gene_ids else 0.0

    evidence_count = len(supporting_interactions)
    evidence_mean_confidence = (
        sum(i.get("confidence_score", 0.0) for i in supporting_interactions) / evidence_count
        if evidence_count else 0.0
    )
    known_target_interaction_score = min(1.0, evidence_mean_confidence * min(1.0, evidence_count / 3))

    return RepurposingFeatures(
        gene_overlap_count=gene_overlap_count,
        gene_overlap_ratio=gene_overlap_ratio,
        target_count=target_count,
        evidence_count=evidence_count,
        evidence_mean_confidence=evidence_mean_confidence,
        compound_similarity_score=compound_similarity_score,
        known_target_interaction_score=known_target_interaction_score,
    )
