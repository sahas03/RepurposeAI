"""
prepare_real_data.py
Run this on your OWN laptop (needs normal internet access to NCBI GEO and
Broad Institute / clue.io) -- NOT inside a network-restricted sandbox.

This is a starter script, not a finished one -- fill in the TODOs with your
actual chosen disease's GEO accession and your downloaded L1000 file paths.

Steps this script performs:
  1. Pull a disease-vs-healthy GEO series and compute a simple DEG table.
  2. Load a downloaded LINCS L1000 GCTX subset and export it to the
     genes x drugs CSV format expected by src/data_loader.py.

Install extra deps for this script only (not needed by the rest of the app):
    pip install GEOparse cmapPy
"""

import pandas as pd
import numpy as np

# ---------------------------------------------------------------------------
# PART 1: Disease signature from GEO
# ---------------------------------------------------------------------------

def build_disease_signature_from_geo(geo_accession: str, disease_group_samples: list[str],
                                       healthy_group_samples: list[str], out_path: str):
    """
    TODO before running:
      - geo_accession: e.g. "GSE55457" (an example RA synovium dataset -- verify
        current availability and relevance on GEO before committing to it)
      - disease_group_samples / healthy_group_samples: GSM sample IDs, found on
        the GEO series page, split into your two comparison groups.

    This does a simple Welch's t-test per gene -- fine for a hackathon MVP.
    For anything more rigorous, use limma/DESeq2 in R if a teammate has that set up.
    """
    import GEOparse
    from scipy import stats

    gse = GEOparse.get_GEO(geo=geo_accession, destdir="./data/raw/geo_cache")

    # Build an expression matrix: rows = genes, columns = samples
    expr = pd.DataFrame(
        {gsm_name: gsm.table.set_index("ID_REF")["VALUE"]
         for gsm_name, gsm in gse.gsms.items()}
    )

    disease_expr = expr[disease_group_samples]
    healthy_expr = expr[healthy_group_samples]

    logFC = disease_expr.mean(axis=1) - healthy_expr.mean(axis=1)
    _, pvals = stats.ttest_ind(disease_expr, healthy_expr, axis=1, equal_var=False)

    out = pd.DataFrame({
        "gene": expr.index,  # NOTE: map probe IDs -> gene symbols using the
                              # platform's GPL annotation table before this step
                              # if your GEO series uses microarray probe IDs
        "logFC": logFC.values,
        "pvalue": pvals,
    }).dropna()

    out.to_csv(out_path, index=False)
    print(f"Wrote disease signature ({len(out)} genes) to {out_path}")


# ---------------------------------------------------------------------------
# PART 2: L1000 matrix from a downloaded GCTX file
# ---------------------------------------------------------------------------

def build_l1000_matrix_from_gctx(gctx_path: str, gene_info_path: str,
                                   sig_info_path: str, out_path: str,
                                   landmark_only: bool = True):
    """
    TODO before running:
      - Download a Level 5 (moderated z-scores, one row per signature) L1000
        GCTX file from clue.io or GEO (GSE92742 / GSE70138), plus its
        accompanying gene_info and sig_info metadata files.
      - gctx_path, gene_info_path, sig_info_path: local paths to those files.

    Filters to landmark genes (the ~978 directly-measured genes, most reliable)
    and exports a plain CSV in the genes x drugs format the pipeline expects.
    """
    from cmapPy.pandasGEXpress.parse import parse

    gene_info = pd.read_csv(gene_info_path, sep="\t")
    sig_info = pd.read_csv(sig_info_path, sep="\t")

    if landmark_only:
        landmark_ids = gene_info[gene_info["pr_is_lm"] == 1]["pr_gene_id"].astype(str).tolist()
        gctoo = parse(gctx_path, rid=landmark_ids)
    else:
        gctoo = parse(gctx_path)

    data = gctoo.data_df  # rows = gene IDs, columns = signature IDs

    # Map gene IDs -> gene symbols
    id_to_symbol = gene_info.set_index("pr_gene_id")["pr_gene_symbol"].to_dict()
    data.index = data.index.astype(int).map(id_to_symbol)
    data = data[~data.index.isna()]

    # Map signature IDs -> compound/drug names, and collapse replicate signatures
    # for the same compound by averaging (simplification for MVP purposes)
    sig_to_drug = sig_info.set_index("sig_id")["pert_iname"].to_dict()
    data.columns = [sig_to_drug.get(c, c) for c in data.columns]
    data = data.groupby(axis=1, level=0).mean()

    data.index.name = "gene"
    data.to_csv(out_path)
    print(f"Wrote L1000 matrix ({data.shape[0]} genes x {data.shape[1]} drugs) to {out_path}")


if __name__ == "__main__":
    print(__doc__)
    print("Fill in the TODOs in this file with your actual GEO accession and")
    print("L1000 file paths, then call the two functions above from a notebook")
    print("or a short __main__ block here.")
