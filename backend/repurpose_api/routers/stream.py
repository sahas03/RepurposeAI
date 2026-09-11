"""GET /api/run/stream -- the same run, reported stage by stage as it happens."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse

from .. import datasets, streaming
from ..schemas import PipelineSettings, ScoringMethod, Weights

router = APIRouter(prefix="/api", tags=["pipeline"])


@router.get(
    "/run/stream",
    summary="Run the pipeline, streaming each stage as it completes (SSE)",
    response_class=StreamingResponse,
    responses={
        200: {
            "content": {"text/event-stream": {}},
            "description": (
                "An SSE stream: one `start` event, one `stage` event per completed stage "
                "carrying its real wall-clock cost, then a terminal `result` event holding "
                "the same PipelineResult that POST /api/run returns. On failure the stream "
                "ends with a `result` event flagged `stale: true` if a precomputed fallback "
                "exists, otherwise an `error` event."
            ),
        }
    },
)
async def run_stream(
    request: Request,
    dataset_id: str = Query("synthetic-benchmark", alias="datasetId"),
    disease_name: str = Query("rheumatoid arthritis", alias="diseaseName"),
    method: ScoringMethod = Query("cosine-fast"),
    display_top_n: int = Query(15, alias="displayTopN", ge=1, le=1000),
    validation_top_k: int = Query(20, alias="validationTopK", ge=1, le=1000),
    weight_reversal: float = Query(0.6, alias="weightReversal"),
    weight_safety: float = Query(0.2, alias="weightSafety"),
    weight_novelty: float = Query(0.2, alias="weightNovelty"),
) -> StreamingResponse:
    """Stream one pipeline run as Server-Sent Events.

    Settings arrive as query parameters because `EventSource` can only issue GET
    requests; they mirror the `PipelineSettings` fields of `POST /api/run` and
    produce an identical result.

    Every run on this endpoint is computed live -- it never serves a cached
    result, because a cached result has no stages left to report.
    """
    # Resolve the dataset up front: once StreamingResponse sends its 200 the
    # status can no longer be changed, so an unknown id must fail before that.
    datasets.get_spec(dataset_id)

    settings = PipelineSettings(
        dataset_id=dataset_id,
        disease_name=disease_name,
        method=method,
        display_top_n=display_top_n,
        validation_top_k=validation_top_k,
        weights=Weights(
            reversal=weight_reversal, safety=weight_safety, novelty=weight_novelty
        ),
    )
    return StreamingResponse(
        streaming.event_stream(settings, request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Tell nginx and friends not to buffer, which would defeat the point.
            "X-Accel-Buffering": "no",
        },
    )
