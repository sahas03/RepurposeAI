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
    """
    genes = disease_vec.index.intersection(drug_vec.index)
    d = disease_vec.loc[genes]
    v = drug_vec.loc[genes]
    contribution = d * v

    out = pd.DataFrame({
        "gene": genes,
        "disease_logFC": d.values,
        "drug_zscore": v.values,
        "contribution": contribution.values,
    }).sort_values("contribution").head(top_n).reset_index(drop=True)

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
            f"of the top {top_n_genes} disease-associated genes examined, including "
            f"{', '.join(genes_df['gene'].head(3).tolist())}."
        ),
    }

    if run_pathways and GSEAPY_AVAILABLE:
        reversed_genes = genes_df[genes_df["direction"] == "reversed by drug"]["gene"].tolist()
        if reversed_genes:
            explanation["pathways"] = pathway_enrichment(reversed_genes)

    return explanation


if __name__ == "__main__":
    print(__doc__)
