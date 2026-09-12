"""
compute_specificity.py
Empirical specificity score: does a drug reverse the RA signature SPECIFICALLY,
or is it just generally loud?

THIS IS NOT TAU. CMap's tau ranks a score against the Touchstone reference bank
(~2,400 curated perturbagens queried against each other), which we do not have --
see scripts/compute_ncs.py. This is an in-house empirical null: each drug is
compared against ITS OWN distribution of scores on random, meaningless queries.
Label it "specificity percentile" or "empirical null percentile" -- never "tau",
and never "the CMap normalization".

WHY THIS AND NOT NCS
--------------------
NCS divides every same-signed score in a cell line by one scalar, so it cannot
re-rank drugs within a cell line (verified: Spearman(raw, NCS) = 1.000000 within
every cell line). It equalizes cell lines, not compounds. The confound here is at
the compound level: proteasome inhibitors and tubulin agents are loud in every
cell line, so they score well against almost any query. A per-drug empirical null
targets exactly that.

METHOD
------
1. Real query = the z-scored RA signature, exactly as the pipeline scores it.
2. Null queries = gene-label permutations of that same vector. A permutation
   preserves the up/down gene counts (6,132 / 5,906) and the magnitude
   distribution EXACTLY, while destroying which gene carries which value --
   i.e. "same size and shape, no real biology".
3. Score every drug against the real query and all null queries (cosine, the same
   metric the main pipeline uses; more negative = stronger reversal).
4. For each drug, locate its real score inside its own null distribution:
       z          = (real - null_mean) / null_sd       <- primary ranking
       pct_below  = fraction of null scores at or below the real score
       emp_p      = (1 + #{null <= real}) / (n_null + 1)   one-sided, reversal
   Ranking uses z rather than the percentile because with 500 nulls the percentile
   saturates at 1/501 for every drug that beats all its nulls; z keeps resolving
   past that point. Both are written out.

Usage:  python scripts/compute_specificity.py [--n-null 500] [--seed 0]
Output: data/processed/specificity_scores_bing.csv   (new file; nothing else touched)
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from data_loader import (  # noqa: E402
    harmonize_genes,
    load_disease_signature,
    load_l1000_matrix,
    zscore_disease_signature,
)
from signature_matching import cosine_reversal_score  # noqa: E402

DATA = os.path.join(ROOT, "data", "processed")


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--n-null", type=int, default=500)
    p.add_argument("--seed", type=int, default=0)
    p.add_argument("--out", default=os.path.join(DATA, "specificity_scores_bing.csv"))
    args = p.parse_args(argv)

    print("1. loading full-space data")
    dis = load_disease_signature(os.path.join(DATA, "disease_signature_bing.csv"))
    l1000 = load_l1000_matrix(os.path.join(DATA, "l1000_matrix_bing.csv.gz"))
    dis, l1000 = harmonize_genes(dis, l1000)
    dvec = zscore_disease_signature(dis)
    print(f"   {len(dvec)} shared genes x {l1000.shape[1]} drugs")

    real = cosine_reversal_score(dvec, l1000)  # pipeline's own scorer
    drugs = l1000.columns

    print(f"2. building {args.n_null} null queries (gene-label permutations)")
    rng = np.random.default_rng(args.seed)
    d = dvec.to_numpy(float)
    Q = rng.permuted(np.tile(d, (args.n_null, 1)), axis=1).T  # genes x nulls
    assert np.allclose(np.sort(Q[:, 0]), np.sort(d)), "permutation must preserve the value multiset"
    print(f"   each null: up {(Q[:, 0] > 0).sum()}, down {(Q[:, 0] < 0).sum()} "
          f"(real: up {(d > 0).sum()}, down {(d < 0).sum()})")

    print("3. scoring every drug against every query")
    t0 = time.perf_counter()
    X = np.ascontiguousarray(l1000.loc[dvec.index].to_numpy(float))
    Xn = X / np.linalg.norm(X, axis=0)
    null_scores = Xn.T @ (Q / np.linalg.norm(Q, axis=0))  # drugs x nulls
    print(f"   {null_scores.shape[0]} x {null_scores.shape[1]} scores in {time.perf_counter() - t0:.1f}s")

    print("4. locating each drug's real score in its own null distribution")
    mean = null_scores.mean(axis=1)
    sd = null_scores.std(axis=1, ddof=1)
    r = real.loc[drugs].to_numpy(float)
    with np.errstate(divide="ignore", invalid="ignore"):
        z = np.where(sd > 0, (r - mean) / sd, 0.0)
    n_below = (null_scores <= r[:, None]).sum(axis=1)
    out = pd.DataFrame({
        "raw_cosine": r,
        "null_mean": mean,
        "null_sd": sd,
        "specificity_z": z,                                   # negative = RA-specific reversal
        "pct_below": n_below / null_scores.shape[1],          # low = real score beats its nulls
        "emp_p": (1 + n_below) / (null_scores.shape[1] + 1),  # one-sided, reversal direction
    }, index=drugs)
    out.index.name = "drug"
    out = out.sort_values("specificity_z")
    out.insert(0, "specificity_rank", np.arange(1, len(out) + 1))
    out.round(6).to_csv(args.out)
    print(f"   wrote {len(out)} drugs -> {os.path.relpath(args.out, ROOT)}")
    print(f"   null means centre on 0 as expected: median {np.median(mean):+.5f} "
          f"(median null sd {np.median(sd):.4f})")
    passed = (out.emp_p <= 0.05).sum()
    print(f"   drugs passing emp_p <= 0.05: {passed} ({passed / len(out):.1%}; ~5% expected by chance)")
    return out


if __name__ == "__main__":
    main()
