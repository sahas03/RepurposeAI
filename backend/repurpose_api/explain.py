"""
explain.py
Gene-level interpretability, wrapping src/interpretability.py.

This is the one capability the browser-side engine cannot provide: the frontend
ports the loader, filters, scoring and validation, but not interpretability.py,
even though engine/types.ts already defines a GeneContribution type waiting for
it. So this endpoint is a real addition rather than a duplicate of in-browser work.

Two things are handled defensively here:

  Enrichr needs internet. Every enrichment call runs in a worker thread with a
  hard timeout, exactly as app/dashboard.py does, so no venue wifi means a
  gene-level explanation with a note attached -- never a hung request.

  Enrichr only recognises real gene SYMBOLS. The synthetic benchmark's
  GENE0000-style placeholders would return nothing, so enrichment is gated OFF
  for synthetic datasets by default and ON once real symbols are in use. Callers
  can override, and the response says which happened.
"""

from __future__ import annotations

import queue
import threading

import pandas as pd

from . import bridge, config, datasets
from .schemas import ExplainResult, GeneContribution, Pathway


class DrugNotFound(Exception):
    """The requested compound is not a column of this dataset's drug matrix."""


def _try_pathway_enrichment(genes: list[str], gene_sets: str) -> tuple[pd.DataFrame | None, str | None]:
    """Best-effort Enrichr call. Never raises: returns (result, note).

    Deliberately a bare daemon thread rather than a ThreadPoolExecutor: the
    executor's context manager calls shutdown(wait=True) on the way out, which
    blocks until the worker finishes and so silently un-does the timeout -- the
    request would still hang for as long as Enrichr does. A daemon thread lets
    the timeout actually bound the request, and lets the process exit even with
    a stuck HTTP call outstanding.
    """
    if not genes:
        return None, "No reversed genes to analyse."
    if not bridge.GSEAPY_AVAILABLE:
        return None, "Pathway enrichment unavailable: gseapy is not installed (pip install gseapy)."

    outcome: queue.Queue = queue.Queue(maxsize=1)

    def work() -> None:
        try:
            outcome.put(("ok", bridge.pathway_enrichment(genes, gene_sets)))
        except Exception as e:  # noqa: BLE001 - a failed lookup must not fail the request
            outcome.put(("error", e))

    threading.Thread(target=work, name="enrichr", daemon=True).start()
    try:
        status, payload = outcome.get(timeout=config.ENRICHR_TIMEOUT)
    except queue.Empty:
        return None, (
            f"Pathway enrichment timed out after {config.ENRICHR_TIMEOUT}s (no internet "
            "access?) -- showing the gene-level explanation only."
        )
    if status == "error":
        return None, f"Pathway enrichment unavailable ({type(payload).__name__}: {payload})."
    return payload, None


def _pathway_rows(df: pd.DataFrame) -> list[Pathway]:
    return [
        Pathway(
            term=str(r["Term"]),
            overlap=str(r["Overlap"]),
            adjusted_p_value=float(r["Adjusted P-value"]),
            genes=str(r["Genes"]),
        )
        for _, r in df.iterrows()
    ]


def explain(
    dataset_id: str,
    drug: str,
    top_n_genes: int = 10,
    run_pathways: bool | None = None,
    gene_sets: str = "KEGG_2021_Human",
) -> ExplainResult:
    """Explain one candidate: which genes drove its score, and optionally which
    pathways those genes belong to.

    run_pathways=None means "decide from the data": on for real gene symbols,
    off for the synthetic benchmark's placeholders.
    """
    prepared = datasets.prepare(dataset_id)

    if drug not in prepared.l1000_df.columns:
        raise DrugNotFound(
            f"{drug!r} is not in dataset {dataset_id!r} "
            f"({len(prepared.l1000_df.columns)} compounds available)."
        )

    disease_vec = bridge.run_stage(
        "z-score disease signature", bridge.zscore_disease_signature, prepared.disease_df
    )

    # Always call through with run_pathways=False; enrichment is run separately
    # below so it can be given a timeout.
    raw = bridge.run_stage(
        "explain candidate",
        bridge.explain_candidate,
        drug,
        disease_vec,
        prepared.l1000_df,
        top_n_genes=top_n_genes,
        run_pathways=False,
    )
    genes_df: pd.DataFrame = raw["top_genes"]

    contributions = [
        GeneContribution(
            gene=str(r["gene"]),
            diseaseLogFC=float(r["disease_logFC"]),
            drug_zscore=float(r["drug_zscore"]),
            contribution=float(r["contribution"]),
            direction=str(r["direction"]),
        )
        for _, r in genes_df.iterrows()
    ]
    reversed_genes = [c.gene for c in contributions if c.direction == "reversed by drug"]

    is_synthetic = prepared.spec.provenance == "synthetic"
    wanted = (not is_synthetic) if run_pathways is None else run_pathways

    pathways = None
    note: str | None = None
    if not wanted:
        note = (
            "Pathway enrichment skipped: this dataset uses placeholder gene identifiers "
            "(GENE0000), which Enrichr does not recognise. It activates automatically once "
            "real gene symbols are loaded."
            if is_synthetic
            else "Pathway enrichment not requested."
        )
    else:
        if is_synthetic:
            note = (
                "Pathway enrichment was requested on synthetic placeholder gene identifiers; "
                "Enrichr will not recognise them, so an empty result here is expected."
            )
        df, failure_note = _try_pathway_enrichment(reversed_genes, gene_sets)
        if df is not None and not df.empty:
            pathways = _pathway_rows(df)
            note = None
        elif df is not None:
            # Ran successfully and found nothing. Say so, rather than returning
            # an empty panel the UI cannot distinguish from "not attempted".
            note = (
                f"Enrichment ran against {gene_sets} over {len(reversed_genes)} reversed "
                "genes and returned no enriched pathways."
            )
        else:
            note = failure_note or note

    return ExplainResult(
        drug=drug,
        summary=str(raw["summary"]),
        top_genes=contributions,
        reversed_count=len(reversed_genes),
        pathways=pathways,
        pathways_note=note,
    )
