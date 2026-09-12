"""
data_loader.py
Loads and harmonizes:
  1. Disease signature (differentially expressed genes: gene, logFC, pvalue)
  2. Drug perturbation signature matrix (LINCS L1000-style: genes x drugs, z-scored)

Expected input formats (produce these from raw downloads before running the pipeline):

disease_signature.csv
    gene,logFC,pvalue
    TNF,2.3,0.0001
    IL6,1.8,0.0003
    ...

l1000_matrix.csv
    gene,drug_1,drug_2,drug_3,...
    TNF,-1.2,0.3,-0.8
    IL6,-0.9,0.1,-1.1
    ...
    (values are z-scored differential expression induced by each drug)

Real-data notes:
  - LINCS L1000 raw files are distributed as .gctx (GCTX/HDF5). Use cmapPy's
    `parse` function to load them, then subset to landmark genes and export
    to the CSV format above. See scripts/prepare_l1000.py for a starter script
    (requires network access to Broad Institute / clue.io, run this LOCALLY,
    not inside a sandboxed environment with restricted egress).
  - Disease signatures: pull a GEO series (disease vs. healthy) with GEOparse,
    run a simple differential expression comparison (or use limma/DESeq2 output
    if your team has access to R), and export gene/logFC/pvalue.
"""

from __future__ import annotations
import csv
import io
import pandas as pd
import numpy as np

# Below this many shared genes a reversal score is not meaningful (with 1 gene,
# cosine gives every drug exactly +/-1). Enforced by harmonize_genes and by the
# scoring functions in signature_matching for callers that skip harmonization.
MIN_SHARED_GENES = 20


def _raw_header(path_or_buf) -> list[str]:
    """First CSV row exactly as written -- before pandas renames duplicates to 'x.1'."""
    if isinstance(path_or_buf, (str, bytes)) or hasattr(path_or_buf, "__fspath__"):
        with open(path_or_buf, newline="", encoding="utf-8-sig") as f:
            return next(csv.reader(f), [])
    pos = path_or_buf.tell()
    line = path_or_buf.readline()
    path_or_buf.seek(pos)
    if isinstance(line, bytes):
        line = line.decode("utf-8-sig")
    return next(csv.reader(io.StringIO(line)), [])


def load_disease_signature(path: str, top_n: int | None = None) -> pd.DataFrame:
    """Load disease DEG table. Optionally keep only the top_n most significant genes."""
    df = pd.read_csv(path)
    required = {"gene", "logFC", "pvalue"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"disease_signature.csv missing columns: {missing}")

    df = df.dropna(subset=["gene", "logFC"])
    df["gene"] = df["gene"].astype(str).str.upper().str.strip()
    df = df.drop_duplicates(subset="gene")

    if top_n is not None:
        df = df.reindex(df["pvalue"].sort_values().index).head(top_n)

    return df.reset_index(drop=True)


def load_l1000_matrix(path: str) -> pd.DataFrame:
    """
    Load drug perturbation signature matrix (genes as rows, drugs as columns).
    Duplicate drug names (case-insensitive) are rejected: pandas would otherwise
    silently rename the second copy to 'name.1', which then escapes the indication
    lookup and can surface an already-indicated drug as a "novel" candidate.
    """
    drugs = pd.Index([c.strip().lower() for c in _raw_header(path)[1:]])
    dupes = sorted(set(drugs[drugs.duplicated()]))
    if dupes:
        raise ValueError(
            f"Duplicate drug columns in L1000 matrix: {dupes[:5]}. Collapse replicate "
            "signatures per drug first (e.g. average them, as prepare_real_data.py does)."
        )
    df = pd.read_csv(path, index_col=0)
    df.index = df.index.astype(str).str.upper().str.strip()
    df = df[~df.index.duplicated(keep="first")]
    return df


def harmonize_genes(disease_df: pd.DataFrame, l1000_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Restrict both datasets to their shared gene set (L1000 landmark genes are
    the usual bottleneck — expect ~500-978 genes to survive this step).
    """
    shared_genes = sorted(set(disease_df["gene"]) & set(l1000_df.index))
    if len(shared_genes) < MIN_SHARED_GENES:
        raise ValueError(
            f"Only {len(shared_genes)} shared genes found between disease signature "
            "and L1000 matrix. Check gene ID formats (both should be HGNC symbols)."
        )

    disease_out = disease_df[disease_df["gene"].isin(shared_genes)].set_index("gene").loc[shared_genes]
    l1000_out = l1000_df.loc[shared_genes]

    return disease_out.reset_index(), l1000_out


def zscore_disease_signature(disease_df: pd.DataFrame) -> pd.Series:
    """Convert logFC column into a z-scored vector indexed by gene."""
    vals = disease_df.set_index("gene")["logFC"]
    sd = vals.std(ddof=0)
    if not np.isfinite(sd) or sd == 0:
        # z-scoring would divide 0 by 0 -> an all-NaN vector -> NaN scores for every drug
        raise ValueError(
            f"Disease signature has zero variance ({len(vals)} gene(s), all logFC equal): "
            "there is no differential expression to reverse."
        )
    z = (vals - vals.mean()) / sd
    return z


if __name__ == "__main__":
    print(__doc__)
