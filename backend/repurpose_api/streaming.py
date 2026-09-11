"""
streaming.py
Server-Sent Events for /api/run/stream.

Each stage is emitted the moment it genuinely finishes, carrying its real
wall-clock cost and a factual readout of what it produced. This is the point of
the endpoint: the frontend's per-stage sequence stops being an animation timed
to look like work and becomes an animation driven by work.

Two deliberate non-features:

  No artificial dwell. The pipeline is fast (~130 ms over the synthetic
  benchmark), so a cinematic pace needs a minimum time on screen per stage --
  but that is a presentation decision and belongs in the UI, which already has
  `dwellMs` for it. Padding the server's timings would corrupt the one number
  here that is supposed to be true.

  No cache reads. A cached result was computed by an earlier request and has no
  stages left to happen; replaying its timings as live events would misreport
  what the machine just did. The stream always computes fresh, and stores the
  result so later /api/run calls stay instant.

Wire format (text/event-stream):

    event: start   data: {"settings": {...}, "stages": [...]}
    event: stage   data: {"id": "signature", "ms": 41.2, "readout": "...", "index": 1, "total": 6}
    ...
    event: result  data: {<the same PipelineResult that POST /api/run returns>}

and on failure, terminally:

    event: error   data: {"stage": "reversal scoring", "type": "ValueError", "message": "..."}

Clients must call `EventSource.close()` after `result` or `error`: EventSource
reconnects automatically on a closed connection, which would otherwise start a
brand new pipeline run every few seconds.
"""

from __future__ import annotations

import asyncio
import json
import logging
import queue
import threading
from typing import AsyncIterator

from fastapi import Request

from . import precompute, service
from .orchestrator import StageReport
from .schemas import STAGE_IDS, PipelineResult, PipelineSettings

log = logging.getLogger("repurpose_api")

#: How long to wait on the worker before emitting a keep-alive comment.
_POLL_SECONDS = 0.5


def sse(event: str, data: str) -> str:
    """One SSE frame. Multi-line payloads need a `data:` prefix per line."""
    body = "".join(f"data: {line}\n" for line in (data.splitlines() or [""]))
    return f"event: {event}\n{body}\n"


def _stage_payload(report: StageReport, index: int) -> str:
    return json.dumps(
        {
            "id": report.id,
            "ms": round(report.ms, 3),
            "readout": report.readout,
            "index": index,
            "total": len(STAGE_IDS),
        }
    )


async def event_stream(settings: PipelineSettings, request: Request) -> AsyncIterator[str]:
    """Drive one run on a worker thread, yielding SSE frames as it progresses."""
    events: queue.Queue = queue.Queue()
    DONE = object()

    def on_stage(report: StageReport) -> None:
        events.put(("stage", report))

    def work() -> None:
        try:
            result = service.run(settings, on_stage=on_stage)
            events.put(("result", result))
        except Exception as e:  # noqa: BLE001 - reported to the client as an event
            events.put(("error", e))
        finally:
            events.put((DONE, None))

    worker = threading.Thread(target=work, name="pipeline-stream", daemon=True)
    worker.start()

    yield sse(
        "start",
        json.dumps(
            {
                "settings": settings.model_dump(by_alias=True, mode="json"),
                "stages": list(STAGE_IDS),
            }
        ),
    )

    stage_index = 0
    try:
        while True:
            try:
                kind, payload = await asyncio.to_thread(events.get, True, _POLL_SECONDS)
            except queue.Empty:
                if await request.is_disconnected():
                    log.info("Client disconnected; abandoning the stream.")
                    return
                # Keep-alive comment: not an event, ignored by EventSource.
                yield ": keep-alive\n\n"
                continue

            if kind is DONE:
                return

            if kind == "stage":
                stage_index += 1
                yield sse("stage", _stage_payload(payload, stage_index))

            elif kind == "result":
                result: PipelineResult = payload
                yield sse("result", result.model_dump_json(by_alias=True))

            elif kind == "error":
                exc: Exception = payload
                # Demo safety, same as POST /api/run: a stored known-good result
                # beats a dead screen, and arrives clearly flagged as a replay.
                reason = f"Live run failed ({type(exc).__name__}: {exc})."
                fallback = precompute.fallback(settings, reason)
                if fallback is not None:
                    log.warning("%s Streaming the last known-good result instead.", reason)
                    yield sse("result", fallback.model_dump_json(by_alias=True))
                else:
                    log.error("Streamed run failed: %s", exc, exc_info=exc)
                    yield sse(
                        "error",
                        json.dumps(
                            {
                                "stage": getattr(exc, "stage", "unexpected"),
                                "type": type(getattr(exc, "original", exc)).__name__,
                                "message": str(exc),
                            }
                        ),
                    )
    finally:
        # Nothing to clean up: the worker is a daemon thread, so a client that
        # vanished mid-run cannot hold the process open.
        pass
