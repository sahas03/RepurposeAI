"""
fusion_sensitivity.py
How sensitive is the final top-20 to the score-fusion weights in
filters.combine_scores (default: 0.6 reversal + 0.2 safety + 0.2 novelty)?

Runs combine_scores (the real function, not a copy) at several weight
combinations and reports, versus the default weights:
  overlap@20  -- how many of the default top-20 drugs are still in the top 20
  in / out    -- drugs that entered / left the top 20
  mean|drank| -- mean absolute rank shift of drugs in both top-20 lists
  tau         -- Kendall's tau of the shared drugs' order (1 = same order)

Two input modes are reported, because on mock data the pipeline's safety and
novelty inputs are CONSTANT (no SMILES lookup / rdkit, and no real RA drug names),
which makes every weight combination rank identically:
  A. "as the pipeline sees it"  -- safety/novelty exactly as the dashboard computes them
  B. "synthetic safety/novelty" -- SYNTHETIC Lipinski-like safety scores and random
     known-RA flags, so you can see the formula's sensitivity. These are not real drug
     properties; rerun mode A on real data for real conclusions.

Usage:
    python scripts/fusion_sensitivity.py                       # large mock data (temp dir)
    python scripts/fusion_sensitivity.py --method wtcs --pool 100
    python scripts/fusion_sensitivity.py --data-dir data/raw   # real data, read-only (mode A only)
"""

from __future__ import annotations

import argparse
import os
import sys
import tempfile

import numpy as np
import pandas as pd
from scipy.stats import kendalltau

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from data_loader import load_disease_signature, load_l1000_matrix, harmonize_genes
from signature_matching import score_reversal, rank_candidates
from filters import apply_novelty_filter, apply_safety_filter, combine_scores, RDKIT_AVAILABLE
from validate import KNOWN_VALIDATION_SETS

DISEASE = "rheumatoid arthritis"
TOP_K = 20

WEIGHT_GRID = {
    "default 0.6/0.2/0.2": {"reversal": 0.6, "safety": 0.2, "novelty": 0.2},
    "reversal-only 1/0/0": {"reversal": 1.0, "safety": 0.0, "novelty": 0.0},
    "reversal-heavy .8/.1/.1": {"reversal": 0.8, "safety": 0.1, "novelty": 0.1},
    "lighter .5/.25/.25": {"reversal": 0.5, "safety": 0.25, "novelty": 0.25},
    "balanced .4/.3/.3": {"reversal": 0.4, "safety": 0.3, "novelty": 0.3},
    "safety-tilt .6/.3/.1": {"reversal": 0.6, "safety": 0.3, "novelty": 0.1},
    "novelty-tilt .6/.1/.3": {"reversal": 0.6, "safety": 0.1, "novelty": 0.3},
}


def build_pool(scores: pd.Series, pool: int, safety: dict | None, known_indications: dict) -> pd.DataFrame:
    """Candidate pool exactly as the dashboard builds it: rank -> novelty -> (safety)."""
    cand = rank_candidates(scores, top_n=pool)
    cand = apply_novelty_filter(cand, known_indications, DISEASE)
    if safety is not None:
        cand["safety_score"] = cand["drug"].map(safety).fillna(0.5)
    return cand


def fused_order(cand: pd.DataFrame, weights: dict) -> list[str]:
    return combine_scores(cand, weights)["drug"].tolist()


def compare(base: list[str], other: list[str], k: int = TOP_K) -> dict:
    b, o = base[:k], other[:k]
    shared = [d for d in b if d in o]
    shifts = [abs(b.index(d) - o.index(d)) for d in shared]
    tau = kendalltau([b.index(d) for d in shared], [o.index(d) for d in shared]).statistic if len(shared) > 1 else np.nan
    return {
        f"overlap@{k}": f"{len(shared)}/{k}",
        "in": len(set(o) - set(b)),
        "out": len(set(b) - set(o)),
        "mean|drank|": round(float(np.mean(shifts)), 2) if shifts else np.nan,
        "max|drank|": max(shifts) if shifts else np.nan,
        "tau": round(float(tau), 3),
    }


def sweep(cand: pd.DataFrame, planted: list[str] | None) -> pd.DataFrame:
    orders = {name: fused_order(cand, w) for name, w in WEIGHT_GRID.items()}
    base = orders["default 0.6/0.2/0.2"]
    rows = []
    for name, order in orders.items():
        row = {"weights (rev/safety/novelty)": name, **compare(base, order)}
        if planted:
            row[f"planted in top{TOP_K}"] = f"{len(set(planted) & set(order[:TOP_K]))}/{len(planted)}"
        rows.append(row)
    return pd.DataFrame(rows)


def pool_sweep(scores, safety, known_indications, pools) -> pd.DataFrame:
    """combine_scores min-max scales reversal WITHIN the pool, so pool size alone shifts the ranking."""
    w = WEIGHT_GRID["default 0.6/0.2/0.2"]
    orders = {p: fused_order(build_pool(scores, p, safety, known_indications), w) for p in pools}
    ref = orders[pools[0]]
    return pd.DataFrame([{"pool size": p, **compare(ref, o)} for p, o in orders.items()])


def synthetic_inputs(drugs, seed: int = 0) -> tuple[dict, dict]:
    """SYNTHETIC safety/novelty -- shaped like the real ones, but not real drug properties."""
    rng = np.random.default_rng(seed)
    # Lipinski score levels (0.25 steps), skewed toward passing, like typical L1000 compounds
    safety = rng.choice([0.25, 0.5, 0.75, 1.0], size=len(drugs), p=[0.05, 0.15, 0.3, 0.5])
    safety = np.where(rng.random(len(drugs)) < 0.3, np.minimum(1.0, safety + 0.2), safety)  # "approved" bonus
    safety = np.where(rng.random(len(drugs)) < 0.2, 0.5, safety)  # unknown SMILES -> neutral 0.5
    known = rng.random(len(drugs)) < 0.05
    return (dict(zip(drugs, safety)),
            {d: {DISEASE} for d, k in zip(drugs, known) if k})


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--data-dir", help="dir with disease_signature.csv + l1000_matrix.csv (read-only). "
                                      "Default: generate large mock data in a temp dir.")
    p.add_argument("--method", default="cosine", choices=["cosine", "wtcs"])
    p.add_argument("--pool", type=int, default=100,
                   help="candidates passed to combine_scores (the dashboard uses max(display, top-K, 20))")
    args = p.parse_args(argv)
    pd.set_option("display.width", 200)

    with tempfile.TemporaryDirectory() as tmp:
        planted = None
        if args.data_dir:
            data_dir = args.data_dir
        else:
            import generate_mock_data_large
            meta = generate_mock_data_large.make_data(tmp)
            data_dir, planted = tmp, meta["planted_reversal"]
            print(f"Using large mock data ({meta['n_genes']} genes x {meta['n_drugs']} drugs)")

        disease_df = load_disease_signature(os.path.join(data_dir, "disease_signature.csv"))
        l1000_df = load_l1000_matrix(os.path.join(data_dir, "l1000_matrix.csv"))
        disease_df, l1000_df = harmonize_genes(disease_df, l1000_df)
        scores = score_reversal(disease_df, l1000_df, method=args.method)
        print(f"Scoring: {args.method}   pool: top {args.pool} by reversal   compare: top {TOP_K} after fusion\n")

        # --- Mode A: inputs exactly as the pipeline computes them ---
        known_real = {d: {DISEASE} for d in KNOWN_VALIDATION_SETS[DISEASE]}
        safety_real = None
        smiles_path = os.path.join(data_dir, "smiles_lookup.csv")
        if os.path.exists(smiles_path) and RDKIT_AVAILABLE:
            smiles_df = pd.read_csv(smiles_path)
            cand = rank_candidates(scores, top_n=len(scores))
            safety_real = dict(zip(cand["drug"], apply_safety_filter(
                cand, dict(zip(smiles_df["drug"], smiles_df["smiles"])))["safety_score"]))
        cand_a = build_pool(scores, args.pool, safety_real, known_real)
        n_known = int(cand_a["known_for_disease"].sum())
        print("=" * 90)
        print("A. AS THE PIPELINE SEES IT")
        print(f"   safety: {'Lipinski via rdkit' if safety_real else 'constant 0.5 (no smiles_lookup.csv and/or rdkit)'}; "
              f"known RA drugs in pool: {n_known}")
        print("=" * 90)
        print(sweep(cand_a, planted).to_string(index=False))
        if safety_real is None and n_known == 0:
            print("-> safety and novelty are constant here, so weights only rescale reversal: the ranking "
                  "CANNOT change.\n   Real sensitivity needs real SMILES + real drug names (see mode B for the formula's behavior).")

        if args.data_dir:
            return

        # --- Mode B: synthetic safety / novelty ---
        safety_syn, known_syn = synthetic_inputs(list(scores.index))
        cand_b = build_pool(scores, args.pool, safety_syn, known_syn)
        print("\n" + "=" * 90)
        print("B. SYNTHETIC safety/novelty inputs (NOT real drug properties -- formula behavior only)")
        print(f"   known RA drugs in pool: {int(cand_b['known_for_disease'].sum())}")
        print("=" * 90)
        print(sweep(cand_b, planted).to_string(index=False))

        print(f"\nPool-size effect at default weights (vs pool={20}), synthetic inputs:")
        pools = [20, 50, 100, 200, len(scores)]
        print(pool_sweep(scores, safety_syn, known_syn, pools).to_string(index=False))

        top = combine_scores(cand_b, WEIGHT_GRID["default 0.6/0.2/0.2"]).head(TOP_K)
        print("\nDefault-weight top 20 (synthetic inputs) -- note how fast reversal stops mattering:")
        print(top[["final_rank", "drug", "reversal_score", "safety_score", "known_for_disease", "final_score"]]
              .to_string(index=False))


if __name__ == "__main__":
    main()
