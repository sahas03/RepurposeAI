"""GET /api/candidates/{drug}/explain -- gene-level rationale for one candidate."""

from __future__ import annotations

from fastapi import APIRouter, Query

from .. import explain as explain_mod
from ..schemas import ExplainResult

router = APIRouter(prefix="/api", tags=["interpretability"])


@router.get(
    "/candidates/{drug}/explain",
    response_model=ExplainResult,
    summary="Explain one candidate's score",
)
def explain_candidate(
    drug: str,
    dataset_id: str = Query("synthetic-benchmark", alias="datasetId"),
    top_n_genes: int = Query(10, alias="topNGenes", ge=1, le=200),
    run_pathways: bool | None = Query(
        None,
        alias="runPathways",
        description=(
            "Force Enrichr pathway enrichment on or off. Default (unset) decides from the "
            "data: on for real gene symbols, off for synthetic placeholder identifiers."
        ),
    ),
    gene_sets: str = Query("KEGG_2021_Human", alias="geneSets"),
) -> ExplainResult:
    """Decompose a drug's reversal score into the genes that produced it.

    Each contribution is `d_i * v_i` -- the disease z-score times the drug's
    z-score for that gene -- so the most negative products are the genes the
    compound reverses most strongly. This is the one part of the pipeline the
    in-browser engine does not implement.
    """
    return explain_mod.explain(
        dataset_id=dataset_id,
        drug=drug,
        top_n_genes=top_n_genes,
        run_pathways=run_pathways,
        gene_sets=gene_sets,
    )
