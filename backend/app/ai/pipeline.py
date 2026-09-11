"""
RepurposingPipeline: the pure computational core of drug repurposing scoring.

This module has no database dependency - app/biotech/drug_repurposing.py
gathers the candidate data from PostgreSQL and hands it to `run()`, which
performs steps 3-10 of the documented pipeline (feature extraction through
explanation generation). Steps 1 (input validation), 2 (preprocessing) and 11
(persistence) live in the biotech/service layer where the DB session is
available.
"""
from dataclasses import dataclass

import numpy as np

from app.ai.explainability.explainer import generate_explanation
from app.ai.feature_engineering.feature_engineering import build_repurposing_features
from app.ai.models.repurposing import get_repurposing_model
from app.ai.ranking.ranking_model import RankingModel


@dataclass
class RepurposingCandidate:
    drug_id: str
    drug_name: str
    target_gene_symbols: set
    target_count: int
    supporting_interactions: list[dict]
    compound_similarity_score: float


class RepurposingPipeline:
    def __init__(self):
        self.model = get_repurposing_model()
        self.ranking_model = RankingModel()

    def run(
        self,
        disease_name: str,
        disease_gene_symbols: set,
        candidates: list[RepurposingCandidate],
        top_k: int = 20,
    ) -> list[dict]:
        if not candidates:
            return []

        scored = []
        feature_rows = []
        for candidate in candidates:
            features = build_repurposing_features(
                disease_gene_ids=disease_gene_symbols,
                drug_target_gene_ids=candidate.target_gene_symbols,
                target_count=candidate.target_count,
                supporting_interactions=candidate.supporting_interactions,
                compound_similarity_score=candidate.compound_similarity_score,
            )
            feature_rows.append(features)

        X = np.array([f.to_vector() for f in feature_rows])
        model_confidences = self.model.predict(X)

        for candidate, features, model_confidence in zip(candidates, feature_rows, model_confidences):
            heuristic_score = (
                0.35 * features.gene_overlap_ratio
                + 0.25 * features.evidence_mean_confidence
                + 0.2 * features.known_target_interaction_score
                + 0.2 * features.compound_similarity_score
            )
            combined_score = float(0.6 * model_confidence + 0.4 * heuristic_score)
            scored.append({
                "key": candidate.drug_id,
                "score": combined_score,
                "confidence": float(model_confidence),
                "candidate": candidate,
                "features": features,
            })

        ranked = self.ranking_model.rank(scored, score_key="score", top_k=top_k)

        results = []
        for r in ranked:
            candidate: RepurposingCandidate = r.payload["candidate"]
            features = r.payload["features"]
            explanation = generate_explanation(
                drug_name=candidate.drug_name,
                disease_name=disease_name,
                features=features,
                score=r.score,
                confidence=r.confidence,
                model_name=self.model.model_name,
                model_version=self.model.model_version,
            )
            results.append({
                "drug_id": candidate.drug_id,
                "score": r.score,
                "confidence": r.confidence,
                "rank": r.rank,
                "features": features.to_dict(),
                "explanation": explanation,
                "model_version": self.model.model_version,
            })
        return results
