"""
orchestrator.py
One pipeline run, stage by stage, using only the functions in repurposeai/src.

The sequence mirrors app/dashboard.py and frontend/src/engine/run.ts exactly,
and every call into src/ goes through app/pipeline.py's run_stage(), so a
single broken stage becomes one clean structured error naming that stage
instead of a raw traceback in front of judges.

Stage ids and their timings keys are the six in run.ts STAGES:
    signature -> library -> reversal -> safety -> explain -> validation

What this module does NOT do: reimplement any scoring, filtering or validation.
Two values in the Candidate response shape (reversalScaled, noveltyBonus) are
recomputed here because filters.combine_scores() uses them internally without
emitting them as columns; the expressions are kept character-for-character
identical to that function, and test_parity.py asserts the fusion result
matches combine_scores' own final_score.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass
from typing import Callable

import pandas as pd

from . import bridge, datasets
from .datasets import PreparedDataset, SafetyTable
from .schemas import (
    METHOD_LABELS,
    Candidate,
    DatasetRef,
    PipelineResult,
    PipelineSettings,
    RecoveryResult,
    ScoredDrug,
    SyntheticCheck,
)


@dataclass
class StageReport:
    """Mirrors StageReport in frontend/src/engine/run.ts."""

    id: str
    ms: float
    readout: str


def _finite(value, field: str) -> float:
    """Reject non-finite numbers loudly rather than emitting JSON the UI can't parse.

    NaN here is not a formatting problem, it is a broken score -- most often a
    drug column containing missing values in the L1000 matrix. Say so.
    """
    v = float(value)
    if not math.isfinite(v):
        raise ValueError(
            f"{field} is {v!r}, which cannot be ranked or serialised. The usual cause is "
            "missing values in the drug matrix: drop or impute NaN columns in "
            "l1000_matrix.csv before scoring."
        )
    return v


def _finite_or_none(value) -> float | None:
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def _known_drug_set(disease_name: str) -> set[str]:
    """validate.KNOWN_VALIDATION_SETS for this disease, lowercased.

    Matches knownDrugSet() in frontend/src/engine/validate.ts, including its
    behaviour for an unknown disease: an empty set, not an error.
    """
    return set(bridge.KNOWN_VALIDATION_SETS.get(disease_name.lower().strip(), set()))


def _known_indications(drugs, known: set[str], disease_name: str) -> dict[str, set[str]]:
    """Build the dict filters.apply_novelty_filter() expects from the reference set.

    apply_novelty_filter looks drugs up by exact name; the frontend compares
    lowercased and stripped. Keying on each candidate's own spelling makes the
    real Python function produce the frontend's case-insensitive semantics
    without touching src/filters.py.
    """
    return {
        str(d): {disease_name}
        for d in drugs
        if str(d).lower().strip() in known
    }


def _candidate_rows(df: pd.DataFrame, weights: dict[str, float]) -> list[Candidate]:
    """Convert combine_scores() output into Candidate models.

    reversal_scaled / novelty_bonus are recomputed with the same expressions
    filters.combine_scores() uses internally (it consumes them without
    returning them). Order-independent, so computing them on the sorted output
    gives identical values.
    """
    if df.empty:
        return []

    r = df["reversal_score"]
    r_scaled = (r.max() - r) / (r.max() - r.min() + 1e-9)
    known_col = df.get("known_for_disease", pd.Series(False, index=df.index))
    novelty_bonus = known_col.map({True: 1.0, False: 0.6})
    has_safety = "safety_score" in df.columns

    out: list[Candidate] = []
    for pos, (_, row) in enumerate(df.iterrows()):
        drug = str(row["drug"])
        known = bool(row.get("known_for_disease", False))
        out.append(
            Candidate(
                drug=drug,
                reversal_score=_finite(row["reversal_score"], f"reversal score for {drug}"),
                rank=int(row["rank"]),
                known_for_disease=known,
                novelty_label=str(
                    row.get(
                        "novelty_label",
                        "known hit (validation evidence)" if known else "novel candidate",
                    )
                ),
                safety_score=_finite_or_none(row["safety_score"]) if has_safety else None,
                reversal_scaled=_finite(r_scaled.iloc[pos], f"scaled reversal for {drug}"),
                novelty_bonus=float(novelty_bonus.iloc[pos]),
                final_score=_finite(row["final_score"], f"final score for {drug}"),
                final_rank=int(row["final_rank"]),
            )
        )
    return out


def run_pipeline(
    settings: PipelineSettings,
    safety_table: SafetyTable | None = None,
    on_stage: Callable[[StageReport], None] | None = None,
) -> PipelineResult:
    """Run every stage and return the full PipelineResult.

    on_stage, when given, is called as each stage completes with its real
    wall-clock cost -- the hook a streaming endpoint would push from.
    """
    timings: dict[str, float] = {}
    reports: list[StageReport] = []

    def emit(stage_id: str, ms: float, readout: str) -> None:
        timings[stage_id] = ms
        report = StageReport(id=stage_id, ms=ms, readout=readout)
        reports.append(report)
        if on_stage is not None:
            on_stage(report)

    # -- 01 signature: load the DEG table, harmonise identifiers, z-score -----
    prepared: PreparedDataset = datasets.prepare(settings.dataset_id)
    t0 = time.perf_counter()
    disease_vec = bridge.run_stage(
        "z-score disease signature", bridge.zscore_disease_signature, prepared.disease_df
    )
    zscore_ms = (time.perf_counter() - t0) * 1000

    genes = prepared.genes
    drugs = prepared.drugs
    emit(
        "signature",
        prepared.timings["disease"] + prepared.timings["harmonize"] + zscore_ms,
        f"{len(genes)} genes harmonised from {prepared.disease_genes_before} "
        "differential-expression rows",
    )

    # -- 02 library: the perturbation matrix being swept ----------------------
    emit(
        "library",
        prepared.timings["matrix"],
        f"{len(drugs)} compound signatures loaded across {len(genes)} genes",
    )

    # -- 03 reversal ---------------------------------------------------------
    # "cosine" and "cosine-fast" are the same call: signature_matching's cosine
    # path is vectorised at the source, so there is no second implementation to
    # dispatch to. The distinction survives only as the UI's method label.
    method = "wtcs" if settings.method == "wtcs" else "cosine"
    # score_reversal rejects extra options for cosine, so only WTCS gets kwargs.
    extra = {"weighted": settings.wtcs_weighted} if method == "wtcs" else {}
    t0 = time.perf_counter()
    all_scores: pd.Series = bridge.run_stage(
        "reversal scoring",
        bridge.score_reversal,
        prepared.disease_df,
        prepared.l1000_df,
        method=method,
        **extra,
    )
    # Deterministic tie ordering. pandas' sort_values() is an unstable
    # quicksort, so compounds on identical scores (WTCS zeroes every drug whose
    # up/down enrichments agree in sign -- 13 of 150 on the synthetic set) can
    # come out in any order, and in a different one run to run. JS's
    # Array.sort is stable, so the frontend keeps them in drug-matrix column
    # order. Re-sorting stably over that same column order makes this endpoint
    # reproducible AND identical to the in-browser engine. No score changes:
    # same values, same set, only the order among exact ties is pinned.
    all_scores = all_scores.reindex(prepared.l1000_df.columns).sort_values(kind="stable")
    emit(
        "reversal",
        (time.perf_counter() - t0) * 1000,
        f"strongest reversal {all_scores.iloc[0]:.4f}, weakest {all_scores.iloc[-1]:.4f}",
    )

    # -- 04 safety + novelty -------------------------------------------------
    t0 = time.perf_counter()
    pool_n = max(settings.display_top_n, settings.validation_top_k, 20)
    known = _known_drug_set(settings.disease_name)

    ranked = bridge.run_stage("rank candidates", bridge.rank_candidates, all_scores, pool_n)
    ranked = bridge.run_stage(
        "novelty filter",
        bridge.apply_novelty_filter,
        ranked,
        _known_indications(ranked["drug"], known, settings.disease_name),
        settings.disease_name,
    )
    if safety_table is not None:
        ranked = bridge.run_stage(
            "safety filter",
            bridge.apply_safety_filter,
            ranked,
            safety_table.smiles,
            safety_table.approved or None,
        )
    weights = settings.weights.model_dump()
    combined = bridge.run_stage("score fusion", bridge.combine_scores, ranked, weights)
    candidates = _candidate_rows(combined, weights)
    emit(
        "safety",
        (time.perf_counter() - t0) * 1000,
        f"{len(candidates)} candidates screened, Lipinski proxy active"
        if safety_table is not None
        else f"{len(candidates)} candidates labelled, Lipinski proxy on standby "
        "(no structure table)",
    )

    # -- 05 explain: per-candidate decomposition is computed on demand --------
    emit(
        "explain",
        0.0,
        f"score decomposition available for all {len(candidates)} candidates",
    )

    # -- 06 validation -------------------------------------------------------
    t0 = time.perf_counter()
    real_signal = bridge.run_stage(
        "validation signal check", bridge.has_real_validation_signal, drugs, known
    )
    recovery_model: RecoveryResult | None = None
    synthetic_model: SyntheticCheck | None = None

    if real_signal:
        raw = bridge.run_stage(
            "known-drug recovery",
            bridge.check_recovery,
            combined,
            settings.disease_name,
            top_k=settings.validation_top_k,
        )
        recovery_model = RecoveryResult(
            disease=raw["disease"],
            top_k=raw["top_k"],
            reference_set_size=raw["reference_set_size"],
            recovered_drugs=[str(d) for d in raw["recovered_drugs"]],
            recovered_count=raw["recovered_count"],
            recovery_rate=float(raw["recovery_rate"]),
            novel_candidates=[str(d) for d in raw["novel_candidates"]],
        )
        readout = (
            f"{recovery_model.recovered_count}/{recovery_model.reference_set_size} known "
            f"{settings.disease_name} drugs recovered in top {settings.validation_top_k}"
        )
    else:
        raw = bridge.run_stage(
            "synthetic ground-truth check",
            bridge.synthetic_ground_truth_check,
            combined,
            drugs,
            settings.validation_top_k,
        )
        if raw is not None:
            # Column order, as validation_helpers and the frontend both produce.
            reinforcing_list = [str(d) for d in raw["reinforcing_planted"]]
            reinforcing = set(reinforcing_list)
            synthetic_model = SyntheticCheck(
                recovered=[str(d) for d in raw["recovered"]],
                recovered_count=raw["recovered_count"],
                planted_total=raw["planted_total"],
                recovery_rate=float(raw["recovery_rate"]),
                reinforcing_planted=reinforcing_list,
                # Filter the candidates already built, exactly as the frontend's
                # syntheticGroundTruth() does. Rebuilding them from the filtered
                # DataFrame would recompute reversalScaled's min-max over just
                # those rows, rescaling the worst compounds to ~1.0.
                reinforcing_ranks=[c for c in candidates if c.drug in reinforcing],
            )
            readout = (
                f"{synthetic_model.recovered_count}/{synthetic_model.planted_total} planted "
                f"reversal signals recovered in top {settings.validation_top_k}"
            )
        else:
            readout = "no reference signal available in this dataset"
    emit("validation", (time.perf_counter() - t0) * 1000, readout)

    return PipelineResult(
        settings=settings,
        dataset=DatasetRef(
            id=prepared.spec.id, label=prepared.spec.label, provenance=prepared.spec.provenance
        ),
        method_label=METHOD_LABELS[settings.method],
        genes_matched=len(genes),
        drugs_scored=len(drugs),
        all_scores=[
            ScoredDrug(drug=str(d), reversal_score=_finite(v, f"reversal score for {d}"))
            for d, v in all_scores.items()
        ],
        candidates=candidates,
        recovery=recovery_model,
        synthetic=synthetic_model,
        timings=timings,
        safety_active=safety_table is not None,
        disease_vec=[_finite(v, f"z-score for {g}") for g, v in disease_vec.items()],
        disease_genes=[str(g) for g in disease_vec.index],
    )
