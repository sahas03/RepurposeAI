"""
test_scale.py
Scale test: run the scoring engine on L1000-sized synthetic data
(scripts/generate_mock_data_large.py: ~1,000 genes x 800 drugs, sparse DEGs,
graded-strength planted drugs) and check correctness, equivalence to the
reference per-drug loop, and runtime.

Run: python tests/test_scale.py      (or: pytest tests/)
Writes only to a temp directory -- never touches data/raw/.
"""

import os
import sys
import tempfile
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import generate_mock_data_large
from data_loader import load_disease_signature, load_l1000_matrix, harmonize_genes, zscore_disease_signature
from signature_matching import cosine_reversal_score, rank_candidates
from interpretability import top_contributing_genes


def _load_large(tmp):
    meta = generate_mock_data_large.make_data(tmp)
    disease_df = load_disease_signature(meta["disease_path"])
    l1000_df = load_l1000_matrix(meta["l1000_path"])
    disease_df, l1000_df = harmonize_genes(disease_df, l1000_df)
    return meta, disease_df, l1000_df, zscore_disease_signature(disease_df)


def _reference_cosine_loop(disease_vec, l1000_df):
    """The original per-drug loop implementation, kept here as ground truth."""
    d = disease_vec.values.astype(float)
    scores = {}
    for drug in l1000_df.columns:
        v = l1000_df.loc[disease_vec.index, drug].values.astype(float)
        n = np.linalg.norm(v)
        scores[drug] = 0.0 if n == 0 else np.dot(d, v) / (np.linalg.norm(d) * n)
    return pd.Series(scores).sort_values()


def _check_planted(scores, meta, label):
    order = list(scores.sort_values().index)
    ranks = {d: order.index(d) + 1 for d in meta["planted_reversal"] + meta["planted_reinforcing"]}
    print(f"[{label}] planted ranks: {ranks}")
    strong = [d for d, (s, _) in meta["planted_reversal_strengths"].items() if s >= 1.0]
    assert all(ranks[d] <= 5 for d in strong), f"[{label}] strong planted drugs not all in top 5"
    assert all(ranks[d] <= 10 for d in meta["planted_reversal"]), f"[{label}] a graded planted drug fell out of top 10"
    n = len(order)
    assert all(ranks[d] > n - 5 for d in meta["planted_reinforcing"]), f"[{label}] reinforcing drug not in bottom 5"


def test_cosine_at_scale():
    with tempfile.TemporaryDirectory() as tmp:
        meta, disease_df, l1000_df, disease_vec = _load_large(tmp)
        assert l1000_df.shape == (meta["n_genes"], meta["n_drugs"])

        t = time.perf_counter()
        scores = cosine_reversal_score(disease_vec, l1000_df)
        elapsed = time.perf_counter() - t
        print(f"cosine on {l1000_df.shape}: {elapsed:.3f}s")
        assert elapsed < 2.0, "cosine scoring unexpectedly slow at L1000 scale"

        ref = _reference_cosine_loop(disease_vec, l1000_df)
        assert np.allclose(scores.loc[ref.index].values, ref.values, atol=1e-12)
        _check_planted(scores, meta, "cosine")

        top = rank_candidates(scores, top_n=20)
        genes_df = top_contributing_genes(disease_vec, l1000_df[top["drug"].iloc[0]], top_n=10)
        assert len(genes_df) == 10
        # The strongest contributors for a planted drug should be the planted DEGs
        assert set(genes_df["gene"]) <= set(meta["deg_genes"])


def _reference_legacy_wtcs(disease_df, l1000_df, up_thresh=1.0, down_thresh=-1.0):
    """The ORIGINAL (pre-vectorization, unweighted KS) WTCS loop, verbatim logic."""
    df = disease_df.set_index("gene")
    up = df[df["logFC"] >= up_thresh].index.tolist()
    down = df[df["logFC"] <= down_thresh].index.tolist()

    def es(ranked, gene_set, n):
        hits = ranked.loc[[g for g in gene_set if g in ranked.index]].sort_values()
        pos = hits.values / n
        k = len(pos)
        a = (np.arange(1, k + 1) / k - pos).max()
        b = (pos - np.arange(0, k) / k).max()
        return a if a > b else -b

    scores = {}
    for drug in l1000_df.columns:
        ranked = l1000_df[drug].rank(ascending=False)
        eu, ed = es(ranked, up, len(ranked)), es(ranked, down, len(ranked))
        scores[drug] = (eu - ed) / 2 if np.sign(eu) != np.sign(ed) else 0.0
    return pd.Series(scores).sort_values()


def _reference_weighted_es(drug_col, gene_set):
    """Naive GSEA weighted (p=1) running-sum ES for one drug, written from the formula."""
    ordered = drug_col.sort_values(ascending=False, kind="stable")
    in_set = ordered.index.isin(gene_set)
    n_r = np.abs(ordered[in_set]).sum()
    n_miss = len(ordered) - in_set.sum()
    running, best = 0.0, 0.0
    for val, hit in zip(ordered.values, in_set):
        running += abs(val) / n_r if hit else -1.0 / n_miss
        if abs(running) > abs(best):
            best = running
    return best


def test_wtcs_at_scale():
    from signature_matching import weighted_connectivity_score, select_query_gene_sets, score_reversal
    with tempfile.TemporaryDirectory() as tmp:
        meta, disease_df, l1000_df, disease_vec = _load_large(tmp)

        t = time.perf_counter()
        wtcs = weighted_connectivity_score(disease_df, l1000_df)
        elapsed = time.perf_counter() - t
        print(f"weighted WTCS on {l1000_df.shape}: {elapsed:.3f}s")
        assert elapsed < 2.0, "WTCS unexpectedly slow at L1000 scale"
        assert wtcs.between(-1, 1).all()
        _check_planted(wtcs, meta, "wtcs")

        # Weighted ES matches a naive per-drug implementation of the GSEA formula
        up, down = select_query_gene_sets(disease_df, l1000_df.index)
        for drug in list(l1000_df.columns[:25]) + meta["planted_reversal"] + meta["planted_reinforcing"]:
            eu = _reference_weighted_es(l1000_df[drug], up)
            ed = _reference_weighted_es(l1000_df[drug], down)
            expected = (eu - ed) / 2 if np.sign(eu) != np.sign(ed) else 0.0
            assert abs(wtcs[drug] - expected) < 1e-10, (drug, wtcs[drug], expected)

        # weighted=False reproduces the original unweighted implementation exactly
        legacy = weighted_connectivity_score(disease_df, l1000_df, weighted=False, max_set_size=None)
        ref = _reference_legacy_wtcs(disease_df, l1000_df)
        assert np.allclose(legacy.loc[ref.index].values, ref.values, atol=1e-12)

        # The method switch routes to the same functions
        assert score_reversal(disease_df, l1000_df, method="wtcs").equals(wtcs)
        assert np.allclose(score_reversal(disease_df, l1000_df, method="cosine").values,
                           cosine_reversal_score(disease_vec, l1000_df).values)


def test_wtcs_chunking_invariant():
    from signature_matching import weighted_connectivity_score
    with tempfile.TemporaryDirectory() as tmp:
        _, disease_df, l1000_df, _ = _load_large(tmp)
        a = weighted_connectivity_score(disease_df, l1000_df, chunk_size=2000)
        b = weighted_connectivity_score(disease_df, l1000_df, chunk_size=37)
        assert np.allclose(a.loc[b.index].values, b.values, atol=1e-12)


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        print("=" * 60, f"\n{t.__name__}\n" + "=" * 60)
        t()
        print("PASSED")
    print(f"\nALL {len(tests)} SCALE TESTS PASSED")


if __name__ == "__main__":
    main()
