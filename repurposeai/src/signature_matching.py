"""
signature_matching.py
Core matching engine: score every drug in the L1000 matrix by how strongly it
REVERSES the disease signature (anti-correlation = good repurposing candidate).

Two scoring methods are provided:
  1. cosine_reversal_score   -- simple, fast, good default for Day 2
  2. weighted_connectivity_score (WTCS) -- closer to the original CMap method,
     use once cosine version is working end-to-end (per the sprint plan: don't
     block the pipeline on this)
"""

from __future__ import annotations
import pandas as pd
import numpy as np


def cosine_reversal_score(disease_vec: pd.Series, l1000_df: pd.DataFrame) -> pd.Series:
    """
    Cosine similarity between disease signature and each drug signature.
    A strongly NEGATIVE score means the drug's induced expression change is the
    mirror image of the disease signature -> candidate for reversal therapy.
    Returns a Series indexed by drug, sorted ascending (most negative = best).
    """
    genes = disease_vec.index
    d = disease_vec.values.astype(float)
    d_norm = np.linalg.norm(d)
    if d_norm == 0:
        raise ValueError("Disease vector has zero norm; check input signature.")

    scores = {}
    for drug in l1000_df.columns:
        v = l1000_df.loc[genes, drug].values.astype(float)
        v_norm = np.linalg.norm(v)
        if v_norm == 0:
            scores[drug] = 0.0
            continue
        cos_sim = np.dot(d, v) / (d_norm * v_norm)
        scores[drug] = cos_sim

    result = pd.Series(scores, name="cosine_similarity").sort_values()
    return result


def weighted_connectivity_score(disease_df: pd.DataFrame, l1000_df: pd.DataFrame,
                                 up_thresh: float = 1.0, down_thresh: float = -1.0) -> pd.Series:
    """
    Simplified Weighted Connectivity Score (WTCS), in the spirit of the CMap
    methodology: split the disease signature into up-regulated and down-regulated
    gene sets, then for each drug compute a Kolmogorov-Smirnov-style enrichment
    of those gene sets within the drug's ranked expression change profile.

    disease_df must have columns: gene, logFC (as produced by data_loader.load_disease_signature)
    """
    df = disease_df.set_index("gene")
    up_genes = df[df["logFC"] >= up_thresh].index.tolist()
    down_genes = df[df["logFC"] <= down_thresh].index.tolist()

    if len(up_genes) == 0 or len(down_genes) == 0:
        raise ValueError(
            f"Thresholds too strict: {len(up_genes)} up genes, {len(down_genes)} down genes. "
            "Loosen up_thresh/down_thresh."
        )

    scores = {}
    for drug in l1000_df.columns:
        ranked = l1000_df[drug].rank(ascending=False)  # rank 1 = most up-regulated by drug
        n = len(ranked)

        es_up = _enrichment_score(ranked, up_genes, n)
        es_down = _enrichment_score(ranked, down_genes, n)

        # Reversal: disease-up genes should be DOWN-regulated by the drug (negative ES),
        # disease-down genes should be UP-regulated by the drug (positive ES).
        # WTCS combines these; a strongly negative wtcs = strong reversal candidate.
        if np.sign(es_up) != np.sign(es_down):
            wtcs = (es_up - es_down) / 2
        else:
            wtcs = 0.0
        scores[drug] = wtcs

    return pd.Series(scores, name="wtcs").sort_values()


def _enrichment_score(ranked: pd.Series, gene_set: list[str], n: int) -> float:
    """Simplified running-sum enrichment score (CMap/GSEA-style), returns a value in [-1, 1]."""
    gene_set = [g for g in gene_set if g in ranked.index]
    if not gene_set:
        return 0.0
    hits = ranked.loc[gene_set].sort_values()
    positions = hits.values / n  # normalized rank positions, 0..1
    # Kolmogorov-Smirnov-style statistic: max deviation of hit CDF from uniform CDF
    k = len(positions)
    step_up = np.arange(1, k + 1) / k
    step_down = np.arange(0, k) / k
    a = (step_up - positions).max()
    b = (positions - step_down).max()
    es = a if a > b else -b
    return es


def rank_candidates(score_series: pd.Series, top_n: int = 20) -> pd.DataFrame:
    """Return the top_n strongest reversal candidates as a tidy DataFrame."""
    out = score_series.sort_values().head(top_n).reset_index()
    out.columns = ["drug", "reversal_score"]
    out["rank"] = np.arange(1, len(out) + 1)
    return out[["rank", "drug", "reversal_score"]]


if __name__ == "__main__":
    print(__doc__)
