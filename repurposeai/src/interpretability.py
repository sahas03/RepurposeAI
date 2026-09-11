"""
interpretability.py
Day 3 afternoon module: explain WHY each candidate scored the way it did.

Two layers, neither requiring a trained neural net:
  1. top_contributing_genes  -- per-drug, which genes drove the cosine similarity
  2. pathway_enrichment      -- what biological pathways those genes belong to
                                 (via gseapy's Enrichr wrapper, needs internet)
"""

from __future__ import annotations
import pandas as pd
import numpy as np

try:
    import gseapy as gp
    GSEAPY_AVAILABLE = True
except ImportError:
    GSEAPY_AVAILABLE = False


def top_contributing_genes(disease_vec: pd.Series, drug_vec: pd.Series, top_n: int = 10) -> pd.DataFrame:
    """
    Per-gene contribution to the cosine similarity between disease and drug vectors.
    Contribution_i = d_i * v_i (element-wise product) -- genes with the most negative
    products are driving the reversal signal most strongly.

    Gene identifiers are treated as opaque labels: any format works (symbols like
    TNF, Entrez IDs, placeholders), matched by label not position, in any order.
    Note "disease_logFC" holds whatever disease_vec contains -- in the pipeline that
    is the z-scored signature from data_loader.zscore_disease_signature.
    """
    for name, s in (("disease_vec", disease_vec), ("drug_vec", drug_vec)):
        dupes = s.index[s.index.duplicated()]
        if len(dupes):
            raise ValueError(
                f"{name} has duplicate gene labels (e.g. {list(dupes[:3])}); collapse them "
                "first (data_loader keeps the first occurrence)."
            )

    genes = disease_vec.index.intersection(drug_vec.index, sort=False)
    if len(genes) == 0:
        raise ValueError(
            "No shared gene labels between disease and drug vectors "
            f"(e.g. {list(disease_vec.index[:3])} vs {list(drug_vec.index[:3])}). "
            "Check both use the same ID type (e.g. HGNC symbols) and case."
        )
    d = disease_vec.loc[genes]
    v = drug_vec.loc[genes]
    contribution = d * v

    out = pd.DataFrame({
        "gene": genes,
        "disease_logFC": d.values,
        "drug_zscore": v.values,
        "contribution": contribution.values,
    }).dropna(subset=["contribution"])
    # Stable sort + label tiebreak -> deterministic order regardless of input gene order
    out = (out.assign(_label=out["gene"].astype(str))
              .sort_values(["contribution", "_label"], kind="mergesort")
              .drop(columns="_label")
              .head(top_n).reset_index(drop=True))

    out["direction"] = np.where(
        out["contribution"] < 0, "reversed by drug", "reinforced by drug (unwanted)"
    )
    return out


def pathway_enrichment(gene_list: list[str], gene_sets: str = "KEGG_2021_Human") -> pd.DataFrame:
    """
    Run Enrichr pathway enrichment on a gene list via gseapy (requires internet access
    to the Enrichr API -- run this from your normal dev machine, not a network-restricted
    sandbox).
    Returns top enriched pathways with adjusted p-values.
    """
    if not GSEAPY_AVAILABLE:
        raise ImportError("gseapy is required for pathway_enrichment(). pip install gseapy")

    enr = gp.enrichr(
        gene_list=gene_list,
        gene_sets=gene_sets,
        outdir=None,
    )
    result = enr.results[["Term", "Overlap", "Adjusted P-value", "Genes"]].sort_values("Adjusted P-value")
    return result.head(10).reset_index(drop=True)


def explain_candidate(drug: str, disease_vec: pd.Series, l1000_df: pd.DataFrame,
                       top_n_genes: int = 10, run_pathways: bool = False) -> dict:
    """
    Convenience wrapper: produce a full explanation block for one ranked candidate,
    ready to drop into the dashboard or the pitch deck.
    """
    drug_vec = l1000_df[drug]
    genes_df = top_contributing_genes(disease_vec, drug_vec, top_n=top_n_genes)

    explanation = {
        "drug": drug,
        "top_genes": genes_df,
        "summary": (
            f"{drug} most strongly reverses {sum(genes_df['direction'] == 'reversed by drug')} "
            f"of the top {len(genes_df)} disease-associated genes examined, including "
            f"{', '.join(genes_df['gene'].head(3).astype(str))}."
        ),
    }

    if run_pathways and GSEAPY_AVAILABLE:
        # Enrichr only recognizes gene SYMBOLS -- placeholder or numeric IDs return no pathways
        reversed_genes = genes_df.loc[genes_df["direction"] == "reversed by drug", "gene"].astype(str).tolist()
        if reversed_genes:
            explanation["pathways"] = pathway_enrichment(reversed_genes)

    return explanation


if __name__ == "__main__":
    print(__doc__)
