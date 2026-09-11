"""
main.py
The FastAPI application: CORS, routers, and the error handling that keeps a
failure in front of judges to one clean sentence.

Run it from the backend/ directory:

    uvicorn repurpose_api.main:app --reload --port 8000

Interactive docs at /docs, machine-readable schema at /openapi.json.
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import bridge, config
from .datasets import DatasetNotFound
from .explain import DrugNotFound
from .routers import candidates, meta, run, stream, validation
from .schemas import ErrorResponse, StageErrorBody

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("repurpose_api")

DESCRIPTION = """
A thin, rigorous HTTP surface over the verified RepurposeAI pipeline.

This service imports `repurposeai/src/*.py` directly and adds no second scoring
engine: the numbers it returns are produced by the same functions the Streamlit
dashboard and the test suite exercise. Response shapes mirror
`frontend/src/engine/types.ts` field-for-field (camelCase), so the existing UI
needs no changes to consume them.

**Endpoints**

* `GET /api/datasets` - dataset descriptors, including the disclosure text shown verbatim in the UI
* `POST /api/run` - one full pipeline run, returning `PipelineResult`
* `GET /api/run/stream` - the same run as Server-Sent Events, one event per stage as it completes
* `GET /api/candidates/{drug}/explain` - gene-level rationale, plus optional pathway enrichment
* `GET /api/validate` - live retrospective validation
* `GET /api/health` - capability report (which optional libraries and datasets are present)
"""

app = FastAPI(
    title=config.API_TITLE,
    version=config.API_VERSION,
    description=DESCRIPTION,
    contact={"name": "RepurposeAI", "url": "https://github.com/sahas03/RepurposeAI"},
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    # No cookies or auth are involved; credentials stay off so a wildcard
    # origin remains valid for an unknown demo machine.
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(meta.router)
app.include_router(run.router)
app.include_router(stream.router)
app.include_router(candidates.router)
app.include_router(validation.router)


def _error(status: int, stage: str, exc: Exception, message: str | None = None) -> JSONResponse:
    body = ErrorResponse(
        error=StageErrorBody(
            stage=stage,
            type=type(exc).__name__,
            message=message or str(exc),
            traceback=getattr(exc, "traceback_str", None) if config.DEBUG else None,
        )
    )
    return JSONResponse(status_code=status, content=body.model_dump(by_alias=True))


@app.exception_handler(bridge.StageError)
async def stage_error_handler(request: Request, exc: bridge.StageError) -> JSONResponse:
    """A pipeline stage failed: name the stage, keep the traceback out of the UI.

    Set REPURPOSEAI_DEBUG=1 to include the full traceback in the response.
    """
    log.error("Stage %r failed: %s", exc.stage, exc.original, exc_info=exc.original)
    return _error(
        500,
        exc.stage,
        exc.original,
        f"The '{exc.stage}' stage failed: {type(exc.original).__name__}: {exc.original}",
    )


@app.exception_handler(DatasetNotFound)
async def dataset_not_found_handler(request: Request, exc: DatasetNotFound) -> JSONResponse:
    return _error(404, "dataset", exc)


@app.exception_handler(DrugNotFound)
async def drug_not_found_handler(request: Request, exc: DrugNotFound) -> JSONResponse:
    return _error(404, "explain", exc)


@app.exception_handler(Exception)
async def unexpected_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Anything not already classified still leaves as the same JSON envelope.

    Without this, an unforeseen failure reaches the browser as an unstructured
    500 the UI cannot render -- the exact "raw traceback in front of judges"
    outcome this service exists to prevent.
    """
    log.exception("Unhandled error serving %s", request.url.path)
    return _error(
        500,
        "unexpected",
        exc,
        f"The request failed unexpectedly: {type(exc).__name__}: {exc}",
    )


@app.get("/", tags=["meta"], summary="Service banner")
def root() -> dict:
    return {
        "service": config.API_TITLE,
        "version": config.API_VERSION,
        "docs": "/docs",
        "openapi": "/openapi.json",
        "health": "/api/health",
    }
