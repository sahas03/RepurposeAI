"""
signature_matching.py
Core matching engine: score every drug in the L1000 matrix by how strongly it
REVERSES the disease signature (anti-correlation = good repurposing candidate).

Two scoring methods are provided, switchable via score_reversal(method=...):
  1. cosine_reversal_score   -- simple, fast, good default for Day 2
  2. weighted_connectivity_score (WTCS) -- rank-based CMap/clue.io method
     (weighted KS enrichment of the disease up/down gene sets per drug)
"""

from __future__ import annotations
import warnings
import pandas as pd
import numpy as np

from data_loader import zscore_disease_signature


def cosine_reversal_score(disease_vec: pd.Series, l1000_df: pd.DataFrame) -> pd.Series:
    """
    Cosine similarity between disease signature and each drug signature.
    A strongly NEGATIVE score means the drug's induced expression change is the
    mirror image of the disease signature -> candidate for reversal therapy.
    Returns a Series indexed by drug, sorted ascending (most negative = best).

    Vectorized (one matrix-vector product over all drugs) -- same math as the
    original per-drug loop, but stays fast at real L1000 scale (~1k genes x
    thousands-to-20k compound signatures).
    """
    genes = disease_vec.index
    d = disease_vec.values.astype(float)
    d_norm = np.linalg.norm(d)
    if d_norm == 0:
        raise ValueError("Disease vector has zero norm; check input signature.")

    v = l1000_df.loc[genes].values.astype(float)  # genes x drugs, aligned to disease_vec
    v_norms = np.linalg.norm(v, axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        cos_sim = (d @ v) / (d_norm * v_norms)
    cos_sim = np.where(v_norms == 0, 0.0, cos_sim)

    return pd.Series(cos_sim, index=l1000_df.columns, name="cosine_similarity").sort_values()


def select_query_gene_sets(disease_df: pd.DataFrame, universe,
                           up_thresh: float = 1.0, down_thresh: float = -1.0,
                           max_set_size: int | None = 150) -> tuple[list[str], list[str]]:
    """
    Pick the disease "query" up/down gene sets for WTCS: genes with logFC beyond the
    thresholds, restricted to `universe` (the drug matrix's genes), strongest first,
    capped at max_set_size per side (CMap/clue.io queries use at most 150 per side --
    without a cap, a real signature with many modest DEGs gives huge, diluted sets).
    """
    lfc = disease_df.drop_duplicates(subset="gene").set_index("gene")["logFC"]
    lfc = lfc[lfc.index.isin(universe)]
    up = lfc[lfc >= up_thresh].sort_values(ascending=False)
    down = lfc[lfc <= down_thresh].sort_values()
    if max_set_size is not None:
        up, down = up.head(max_set_size), down.head(max_set_size)

    if len(up) == 0 or len(down) == 0:
        raise ValueError(
            f"Thresholds too strict: {len(up)} up genes, {len(down)} down genes. "
            "Loosen up_thresh/down_thresh."
        )
    if min(len(up), len(down)) < 10:
        warnings.warn(
            f"WTCS query gene sets are small ({len(up)} up, {len(down)} down); "
            "enrichment scores will be noisy. Consider loosening the thresholds."
        )
    return up.index.tolist(), down.index.tolist()


def weighted_connectivity_score(disease_df: pd.DataFrame, l1000_df: pd.DataFrame,
                                 up_thresh: float = 1.0, down_thresh: float = -1.0,
                                 max_set_size: int | None = 150, weighted: bool = True,
                                 chunk_size: int = 2000) -> pd.Series:
    """
    Weighted Connectivity Score (WTCS), as in CMap / clue.io (Subramanian et al. 2017):
    split the disease signature into up- and down-regulated query gene sets, then for
    each drug compute a GSEA-style enrichment score (ES) of each set within the drug's
    ranked expression profile, where each gene's step is weighted by |drug z-score|.

        WTCS = (ES_up - ES_down) / 2   if sign(ES_up) != sign(ES_down), else 0

    Strongly NEGATIVE WTCS = disease-up genes pushed down and disease-down genes pushed
    up by the drug = strong reversal candidate (same convention as cosine).

    weighted=False gives the unweighted Kolmogorov-Smirnov connectivity score of the
    original CMap (Lamb et al. 2006) -- this is what earlier versions of this function
    computed.

    Not included: CMap's normalization of WTCS -> NCS / tau (needs per-cell-line and
    per-perturbagen-type reference distributions from the full L1000 metadata).

    disease_df must have columns: gene, logFC (as produced by data_loader.load_disease_signature)
    Vectorized over drugs, processed in chunks of chunk_size to bound memory.
    """
    up_genes, down_genes = select_query_gene_sets(disease_df, l1000_df.index,
                                                  up_thresh, down_thresh, max_set_size)
    up_mask = l1000_df.index.isin(up_genes)
    down_mask = l1000_df.index.isin(down_genes)

    if weighted:
        es_up, es_down = _weighted_es(l1000_df.values.astype(float), [up_mask, down_mask], chunk_size)
    else:
        ranks = l1000_df.rank(ascending=False).values  # rank 1 = most up-regulated by drug
        es_up = _ks_es(ranks, up_mask)
        es_down = _ks_es(ranks, down_mask)

    # Reversal: disease-up genes should be DOWN-regulated by the drug (negative ES),
    # disease-down genes should be UP-regulated by the drug (positive ES).
    wtcs = np.where(np.sign(es_up) != np.sign(es_down), (es_up - es_down) / 2, 0.0)
    return pd.Series(wtcs, index=l1000_df.columns, name="wtcs").sort_values()


def _weighted_es(z: np.ndarray, gene_sets: list[np.ndarray], chunk_size: int) -> list[np.ndarray]:
    """
    Weighted (GSEA, p=1) enrichment score of each gene set (boolean masks over
    genes) in every drug column of z (genes x drugs). Walk genes from most up- to
    most down-regulated by the drug: hits step up by |z| / (sum of |z| over hits),
    misses step down by 1 / (n - k). ES is the running sum's maximum deviation from
    zero (signed). Returns one array of per-drug ES values per gene set.
    Each drug is sorted once and reused for all gene sets.
    """
    n, m = z.shape
    outs = [np.zeros(m) for _ in gene_sets]
    for start in range(0, m, chunk_size):
        block = z[:, start:start + chunk_size]
        cols = np.arange(block.shape[1])
        order = np.argsort(-block, axis=0, kind="stable")  # row 0 = most up-regulated by drug
        abs_sorted = np.abs(np.take_along_axis(block, order, axis=0))
        for in_set, out in zip(gene_sets, outs):
            hit = in_set[order]
            w = abs_sorted * hit
            w_total = w.sum(axis=0)
            with np.errstate(divide="ignore", invalid="ignore"):
                running = np.cumsum(w, axis=0) / w_total - np.cumsum(~hit, axis=0) / (n - in_set.sum())
            es = running[np.abs(running).argmax(axis=0), cols]
            out[start:start + block.shape[1]] = np.where(w_total > 0, es, 0.0)
    return outs


def _ks_es(ranks: np.ndarray, in_set: np.ndarray) -> np.ndarray:
    """
    Unweighted KS enrichment score (Lamb et al. 2006) for every drug column.
    ranks: genes x drugs, 1 = most up-regulated. Returns values in [-1, 1].
    """
    n = ranks.shape[0]
    positions = np.sort(ranks[in_set], axis=0) / n  # k x drugs, normalized hit positions
    k = positions.shape[0]
    j = np.arange(1, k + 1)[:, None]
    a = (j / k - positions).max(axis=0)
    b = (positions - (j - 1) / k).max(axis=0)
    return np.where(a > b, a, -b)


SCORING_METHODS = ("cosine", "wtcs")


def score_reversal(disease_df: pd.DataFrame, l1000_df: pd.DataFrame,
                   method: str = "cosine", **kwargs) -> pd.Series:
    """
    Single entry point for reversal scoring, switchable by `method`:
      "cosine" (default) -- cosine_reversal_score on the z-scored disease signature
      "wtcs"             -- weighted_connectivity_score; kwargs pass through
                            (up_thresh, down_thresh, max_set_size, weighted, ...)
    disease_df: harmonized gene/logFC table. Both methods return a Series in [-1, 1],
    sorted ascending, most negative = strongest reversal -- so rank_candidates,
    validate.check_recovery and filters.screen_drugs work unchanged with either.
    """
    if method == "cosine":
        if kwargs:
            raise TypeError(f"cosine scoring takes no extra options, got {sorted(kwargs)}")
        return cosine_reversal_score(zscore_disease_signature(disease_df), l1000_df)
    if method == "wtcs":
        return weighted_connectivity_score(disease_df, l1000_df, **kwargs)
    raise ValueError(f"Unknown scoring method {method!r}; choose from {SCORING_METHODS}")


def rank_candidates(score_series: pd.Series, top_n: int = 20) -> pd.DataFrame:
    """Return the top_n strongest reversal candidates as a tidy DataFrame."""
    out = score_series.sort_values().head(top_n).reset_index()
    out.columns = ["drug", "reversal_score"]
    out["rank"] = np.arange(1, len(out) + 1)
    return out[["rank", "drug", "reversal_score"]]


if __name__ == "__main__":
    print(__doc__)
