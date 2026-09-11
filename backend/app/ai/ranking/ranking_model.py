"""Ranks scored candidates and normalizes scores/confidence into [0, 1]."""
from dataclasses import dataclass


@dataclass
class RankedCandidate:
    key: str
    score: float
    confidence: float
    rank: int
    payload: dict


class RankingModel:
    model_name = "ranking_model"
    model_version = "1.0.0"

    @staticmethod
    def rank(candidates: list[dict], score_key: str = "score", top_k: int | None = None) -> list[RankedCandidate]:
        if not candidates:
            return []
        scores = [c[score_key] for c in candidates]
        lo, hi = min(scores), max(scores)
        spread = (hi - lo) or 1.0

        ordered = sorted(candidates, key=lambda c: c[score_key], reverse=True)
        if top_k:
            ordered = ordered[:top_k]

        ranked = []
        for idx, cand in enumerate(ordered, start=1):
            normalized = (cand[score_key] - lo) / spread
            ranked.append(
                RankedCandidate(
                    key=cand.get("key", str(idx)),
                    score=round(float(cand[score_key]), 6),
                    confidence=round(float(cand.get("confidence", normalized)), 6),
                    rank=idx,
                    payload=cand,
                )
            )
        return ranked
