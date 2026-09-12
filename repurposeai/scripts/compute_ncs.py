"""
compute_ncs.py
Normalized Connectivity Score (NCS) for the RA query, per Subramanian et al. 2017.

WHAT THIS IS
------------
Raw cosine/WTCS scores are not comparable across perturbations: some cell lines
and some compounds are transcriptionally "loud" (large, generic disruption), so
raw reversal scores favour antiproliferatives over specific reversers. CMap
corrects this by normalizing each signature's raw score against the distribution
of scores from perturbations in the SAME cell line and perturbation type:

    NCS(s, q) = WTCS(s, q) / | mean( WTCS of same SIGN, same cell line, same pert type ) |

Our pool is entirely trt_cp, so the (cell line x pert type) stratification
collapses to cell line here. That is a property of this dataset, not a shortcut.

WHAT THIS IS NOT
----------------
This is NOT tau. Tau additionally ranks a query's NCS against a reference bank of
NCS values from many OTHER, unrelated disease queries. We have exactly one disease
query (RA), so tau is not computable here and nothing in this output should be
described as "tau" or "the full CMap normalization".

ORDER OF OPERATIONS (this is the substantive change)
----------------------------------------------------
The existing pipeline averages each compound's z-scores across cell lines FIRST,
then scores the averaged profile once. NCS requires the opposite order: score every
signature individually, normalize within its own cell line, and only then aggregate
per compound. Both orders are reported below so the two effects can be told apart.

Usage:
    python scripts/compute_ncs.py --gctx D:/lincs_cache/GSE70138_Level5.gctx
Outputs (new files, nothing existing is modified):
    data/processed/ncs_scores_bing.csv          per-compound raw / NCS scores
    data/processed/ncs_per_signature_bing.csv   per-signature scores + cell line
"""

from __future__ import annotations

import argparse
import os
import sys
import time

import h5py
import numpy as np
import pandas as pd

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
from data_loader import load_disease_signature, zscore_disease_signature  # noqa: E402

DATA = os.path.join(ROOT, "data", "processed")
CACHE = "D:/lincs_cache"
SIG_INFO = f"{CACHE}/GSE70138_Broad_LINCS_sig_info_2017-03-06.txt.gz"
GENE_INFO = f"{CACHE}/GSE70138_Broad_LINCS_gene_info_2017-03-06.txt.gz"


def per_signature_cosine(gctx_path: str, disease_vec: pd.Series, chunk: int = 5000):
    """Cosine similarity of every L1000 signature against the RA disease vector."""
    gi = pd.read_csv(GENE_INFO, sep="\t")
    id2sym = dict(zip(gi.pr_gene_id.astype(str), gi.pr_gene_symbol.astype(str).str.upper()))
    with h5py.File(gctx_path, "r") as f:
        row_ids = [s.decode() for s in f["0/META/ROW/id"][:]]
        sig_ids = [s.decode() for s in f["0/META/COL/id"][:]]
        syms = pd.Index([id2sym.get(r, "") for r in row_ids])
        # columns of the gctx matrix that correspond to genes in the disease signature
        keep = pd.Series(range(len(syms)), index=syms)
        keep = keep[keep.index.isin(disease_vec.index) & ~keep.index.duplicated()]
        cols = keep.to_numpy()
        d = disease_vec.loc[keep.index].to_numpy(dtype=float)
        d_norm = np.linalg.norm(d)
        print(f"  scoring on {len(cols)} shared genes (of {len(syms)} in L1000, {len(disease_vec)} in signature)")

        M = f["0/DATA/0/matrix"]
        out = np.empty(M.shape[0], dtype=np.float64)
        t0 = time.time()
        for start in range(0, M.shape[0], chunk):
            stop = min(start + chunk, M.shape[0])
            X = np.asarray(M[start:stop, :], dtype=np.float32)[:, cols].astype(np.float64)
            norms = np.linalg.norm(X, axis=1)
            with np.errstate(divide="ignore", invalid="ignore"):
                out[start:stop] = (X @ d) / (norms * d_norm)
            out[start:stop] = np.where(norms == 0, 0.0, out[start:stop])
            print(f"    {stop}/{M.shape[0]} signatures ({time.time() - t0:.0f}s)", end="\r")
    print()
    return pd.Series(out, index=sig_ids, name="raw_cosine")


def normalize_ncs(df: pd.DataFrame, score_col: str = "raw_cosine") -> pd.DataFrame:
    """
    CMap 2017 NCS: divide each score by the absolute mean of the same-signed scores
    within its own (cell line, pert type) population. Positive and negative scores are
    normalized separately, which is what makes "loud" cell lines comparable to quiet ones.
    """
    out = df.copy()
    grp = out.groupby(["cell_id", "pert_type", np.sign(out[score_col])])[score_col]
    signed_mean = grp.transform("mean").abs()
    out["ncs"] = np.where(signed_mean > 0, out[score_col] / signed_mean, 0.0)
    return out


def max_quantile(x: np.ndarray) -> float:
    """CMap's across-cell-line summary: the more extreme of the 67th / 33rd percentile."""
    hi, lo = np.percentile(x, 67), np.percentile(x, 33)
    return hi if abs(hi) > abs(lo) else lo


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--gctx", default=f"{CACHE}/GSE70138_Level5.gctx")
    p.add_argument("--disease", default=os.path.join(DATA, "disease_signature_bing.csv"))
    p.add_argument("--chunk", type=int, default=5000)
    args = p.parse_args(argv)

    print("1. RA disease signature")
    dis = load_disease_signature(args.disease)
    dvec = zscore_disease_signature(dis)
    print(f"   {len(dvec)} genes")

    print("2. per-signature cosine against every L1000 signature")
    raw = per_signature_cosine(args.gctx, dvec, args.chunk)

    print("3. attaching cell-line metadata")
    si = pd.read_csv(SIG_INFO, sep="\t", low_memory=False).set_index("sig_id")
    df = si.join(raw.rename("raw_cosine"), how="inner")
    df = df[df.pert_type == "trt_cp"].copy()
    print(f"   {len(df)} trt_cp signatures across {df.cell_id.nunique()} cell lines")

    print("4. NCS normalization (within cell line x pert type)")
    df = normalize_ncs(df)

    per_sig = df[["pert_iname", "cell_id", "pert_idose", "pert_itime", "raw_cosine", "ncs"]]
    per_sig.to_csv(os.path.join(DATA, "ncs_per_signature_bing.csv"))

    print("5. aggregating per compound")
    g = df.groupby("pert_iname")
    scores = pd.DataFrame({
        "n_sig": g.size(),
        "n_cell": g.cell_id.nunique(),
        "raw_cosine_median": g.raw_cosine.median(),
        "ncs_median": g.ncs.median(),
        "ncs_maxq": g.ncs.apply(lambda x: max_quantile(x.to_numpy())),
    })
    scores.index.name = "drug"
    scores.to_csv(os.path.join(DATA, "ncs_scores_bing.csv"))
    print(f"   wrote {len(scores)} compounds -> data/processed/ncs_scores_bing.csv")
    return scores


if __name__ == "__main__":
    main()
