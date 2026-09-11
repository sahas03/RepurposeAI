"""GET /api/validate -- re-run the recovery check live."""

from __future__ import annotations

from fastapi import APIRouter, Query

from .. import service
from ..schemas import PipelineSettings, ScoringMethod, ValidationResult, Weights

router = APIRouter(prefix="/api", tags=["validation"])


@router.get("/validate", response_model=ValidationResult, summary="Retrospective validation")
def validate(
    dataset_id: str = Query("synthetic-benchmark", alias="datasetId"),
    disease_name: str = Query("rheumatoid arthritis", alias="diseaseName"),
    method: ScoringMethod = Query("cosine-fast"),
    top_k: int = Query(20, alias="topK", ge=1, le=1000),
    display_top_n: int = Query(15, alias="displayTopN", ge=1, le=1000),
) -> ValidationResult:
    """Check whether the ranking recovers drugs already known to treat the disease.

    Wraps `validate.check_recovery()` against `KNOWN_VALIDATION_SETS`, so the
    recovery rate can be re-run in front of judges instead of only shown as a
    static slide. On a library of placeholder compounds there are no real drug
    names to recover, so the planted-signal check is reported instead -- the two
    are returned in separate fields and never conflated.
    """
    settings = PipelineSettings(
        dataset_id=dataset_id,
        disease_name=disease_name,
        method=method,
        display_top_n=display_top_n,
        validation_top_k=top_k,
        weights=Weights(),
    )
    return service.validate(settings)
