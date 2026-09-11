"""POST /api/run -- one full pipeline run."""

from __future__ import annotations

from fastapi import APIRouter, Query

from .. import service
from ..schemas import PipelineResult, RunRequest

router = APIRouter(prefix="/api", tags=["pipeline"])


@router.post("/run", response_model=PipelineResult, summary="Run the full pipeline")
def post_run(
    body: RunRequest,
    refresh: bool = Query(
        False, description="Bypass the result cache and recompute from the CSVs."
    ),
) -> PipelineResult:
    """Score every compound against the disease signature and return the full result.

    The response satisfies the `PipelineResult` interface in
    `frontend/src/engine/types.ts` exactly, so an HTTP client implementation of
    `RepurposeClient` can return it unchanged.

    Body is `{datasetId, settings}`; `datasetId` may be omitted when
    `settings.datasetId` is set. Omit the body entirely to run the frontend's
    default settings.
    """
    settings = body.settings
    if body.dataset_id and body.dataset_id != settings.dataset_id:
        settings = settings.model_copy(update={"dataset_id": body.dataset_id})
    return service.run(settings, use_cache=not refresh)
