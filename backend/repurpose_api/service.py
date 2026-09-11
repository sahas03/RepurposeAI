"""
service.py
Application layer: cache lookup, the run itself, and the demo-safety fallback.

Every endpoint goes through here rather than calling the orchestrator directly,
so caching and fallback behaviour are defined in exactly one place.
"""

from __future__ import annotations

import logging
from typing import Callable

from . import caching, datasets, precompute
from .orchestrator import StageReport, run_pipeline
from .schemas import (
    PipelineResult,
    PipelineSettings,
    RecoveryResult,
    SyntheticCheck,
    ValidationResult,
)

log = logging.getLogger("repurpose_api")


def run(
    settings: PipelineSettings,
    use_cache: bool = True,
    on_stage: Callable[[StageReport], None] | None = None,
) -> PipelineResult:
    """Run the pipeline for these settings, or return an equivalent cached result.

    On failure, falls back to the last known-good precomputed result flagged
    `stale: true` when one exists (see precompute.py); otherwise the error
    propagates and is rendered as a structured stage error.

    `on_stage` receives each stage's real result and timing as it completes.
    Passing it forces a live computation: a cached result was produced by an
    earlier request and has no stages left to report, and replaying its timings
    as if they were happening now would be a lie about what the machine just did.
    """
    # Resolves the dataset first: an unknown or unavailable id is a client
    # error and must surface as a 404, never as a stale replay.
    key = caching.result_key(settings)

    if use_cache and on_stage is None:
        hit = caching.get(key)
        if hit is not None:
            return hit

    try:
        result = run_pipeline(
            settings, safety_table=datasets.load_safety_table(), on_stage=on_stage
        )
    except datasets.DatasetNotFound:
        raise
    except Exception as e:  # noqa: BLE001 - deliberate: protect the live demo
        reason = f"Live run failed ({type(e).__name__}: {e})."
        fallback = precompute.fallback(settings, reason)
        if fallback is not None:
            log.warning("%s Serving the last known-good precomputed result.", reason)
            return fallback
        raise

    caching.put(key, result)
    return result


def validate(settings: PipelineSettings) -> ValidationResult:
    """Re-run the recovery check live, so the validation slide can be proven on demand."""
    result = run(settings)
    return ValidationResult(
        dataset=result.dataset,
        disease=settings.disease_name,
        method_label=result.method_label,
        top_k=settings.validation_top_k,
        recovery=result.recovery,
        synthetic=result.synthetic,
        statement=statement_for(result.recovery, result.synthetic, settings),
    )


def statement_for(
    recovery: RecoveryResult | None,
    synthetic: SyntheticCheck | None,
    settings: PipelineSettings,
) -> str:
    """One honest sentence for the pitch, never conflating the two checks."""
    if recovery is not None:
        # Reuses validate.format_validation_statement() rather than rewording it.
        from . import bridge

        return bridge.format_validation_statement(
            {
                "disease": recovery.disease,
                "top_k": recovery.top_k,
                "reference_set_size": recovery.reference_set_size,
                "recovered_drugs": recovery.recovered_drugs,
                "recovered_count": recovery.recovered_count,
                "recovery_rate": recovery.recovery_rate,
                "novel_candidates": recovery.novel_candidates,
            }
        )

    if synthetic is not None:
        held_out = len(synthetic.reinforcing_planted) - len(synthetic.reinforcing_ranks)
        return (
            f"Synthetic benchmark check (not a real-drug result): {synthetic.recovered_count}/"
            f"{synthetic.planted_total} planted reversal signals were recovered in the top "
            f"{settings.validation_top_k}, and {held_out} of "
            f"{len(synthetic.reinforcing_planted)} planted reinforcing compounds stayed out of "
            "that shortlist. These are placeholder identifiers, not drug names -- real "
            "known-drug recovery requires a library containing real compounds."
        )

    return (
        f"No reference signal is available in this dataset for {settings.disease_name}: it "
        "contains neither known reference drugs nor the planted-signal naming convention, so "
        "no recovery claim can be made from it."
    )


def warm(settings: PipelineSettings) -> PipelineResult:
    """Compute and cache a result ahead of time (used by scripts/precompute_demo.py)."""
    return run(settings, use_cache=False)


__all__ = ["run", "validate", "warm", "statement_for", "StageReport"]
