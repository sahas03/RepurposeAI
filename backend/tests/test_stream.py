"""
GET /api/run/stream -- Server-Sent Events.

These assert the stream is driven by real computation: the stage events arrive
in pipeline order, each carries a real timing, and the terminal result is
identical to what the non-streaming endpoint produces for the same settings.
"""

from __future__ import annotations

import json

import pytest

from repurpose_api import caching, precompute, service
from repurpose_api.schemas import STAGE_IDS, PipelineSettings

from .conftest import DATASET, PLANTED_REVERSAL


def collect(client, url: str = f"/api/run/stream?datasetId={DATASET}") -> list[tuple[str, dict]]:
    """Read a stream to completion, returning [(event name, parsed data), ...]."""
    events: list[tuple[str, dict]] = []
    with client.stream("GET", url) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")

        name: str | None = None
        data: list[str] = []
        for line in response.iter_lines():
            if line.startswith(":"):  # keep-alive comment
                continue
            if line.startswith("event: "):
                name = line[len("event: ") :]
            elif line.startswith("data: "):
                data.append(line[len("data: ") :])
            elif line == "":
                if name is not None:
                    events.append((name, json.loads("".join(data))))
                name, data = None, []
    return events


def test_stream_reports_every_stage_in_order(client):
    events = collect(client)
    assert [n for n, _ in events] == ["start"] + ["stage"] * len(STAGE_IDS) + ["result"]

    stages = [d for n, d in events if n == "stage"]
    assert [s["id"] for s in stages] == list(STAGE_IDS)
    for i, s in enumerate(stages, start=1):
        assert s["index"] == i
        assert s["total"] == len(STAGE_IDS)
        assert isinstance(s["ms"], (int, float)) and s["ms"] >= 0
        assert s["readout"], "every stage must say what it actually produced"


def test_stage_readouts_describe_the_real_computation(client):
    stages = {d["id"]: d for n, d in collect(client) if n == "stage"}
    assert "200 genes harmonised" in stages["signature"]["readout"]
    assert "150 compound signatures loaded" in stages["library"]["readout"]
    assert "strongest reversal" in stages["reversal"]["readout"]
    assert "3/3 planted reversal signals recovered" in stages["validation"]["readout"]


def test_start_event_announces_the_settings_and_stage_list(client):
    name, data = collect(client)[0]
    assert name == "start"
    assert data["stages"] == list(STAGE_IDS)
    assert data["settings"]["datasetId"] == DATASET


def test_streamed_result_matches_the_non_streaming_endpoint(client):
    streamed = [d for n, d in collect(client) if n == "result"][0]
    posted = client.post("/api/run", json={"datasetId": DATASET}).json()

    assert streamed["candidates"] == posted["candidates"]
    assert streamed["allScores"] == posted["allScores"]
    assert streamed["synthetic"] == posted["synthetic"]
    assert {c["drug"] for c in streamed["candidates"][:3]} == set(PLANTED_REVERSAL)


def test_streamed_timings_match_the_stage_events(client):
    events = collect(client)
    stages = {d["id"]: d["ms"] for n, d in events if n == "stage"}
    result = [d for n, d in events if n == "result"][0]
    for stage_id, ms in stages.items():
        # The event carries the same measurement the result reports, rounded.
        assert result["timings"][stage_id] == pytest.approx(ms, abs=1e-3)


@pytest.mark.parametrize("method", ["cosine", "cosine-fast", "wtcs"])
def test_stream_honours_the_scoring_method(client, method):
    events = collect(client, f"/api/run/stream?datasetId={DATASET}&method={method}")
    result = [d for n, d in events if n == "result"][0]
    assert result["settings"]["method"] == method
    assert {c["drug"] for c in result["candidates"][:3]} == set(PLANTED_REVERSAL)


def test_stream_honours_weights_and_top_n(client):
    events = collect(
        client,
        f"/api/run/stream?datasetId={DATASET}&displayTopN=25&validationTopK=10"
        "&weightReversal=0.8&weightSafety=0.1&weightNovelty=0.1",
    )
    result = [d for n, d in events if n == "result"][0]
    assert result["settings"]["weights"] == {"reversal": 0.8, "safety": 0.1, "novelty": 0.1}
    assert len(result["candidates"]) == 25


def test_stream_never_serves_a_cached_result(client):
    """A cached result has no stages left to report, so the stream must recompute."""
    client.post("/api/run", json={"datasetId": DATASET})  # warm the cache
    events = collect(client)
    result = [d for n, d in events if n == "result"][0]
    assert result["cached"] is False
    assert len([n for n, _ in events if n == "stage"]) == len(STAGE_IDS)


def test_unknown_dataset_is_a_404_not_a_stream(client):
    """The status must be settled before the 200 of a stream is committed."""
    r = client.get("/api/run/stream?datasetId=no-such-dataset")
    assert r.status_code == 404
    assert not r.headers["content-type"].startswith("text/event-stream")


def test_failure_emits_an_error_event(client, monkeypatch):
    from repurpose_api import bridge

    def explode(*a, **k):
        raise bridge.StageError("reversal scoring", ValueError("matrix is not numeric"))

    monkeypatch.setattr(service, "run_pipeline", explode)
    monkeypatch.setattr(precompute, "fallback", lambda *a, **k: None)
    caching.clear()

    events = collect(client)
    assert [n for n, _ in events] == ["start", "error"]
    error = events[-1][1]
    assert error["stage"] == "reversal scoring"
    assert error["type"] == "ValueError"


def test_failure_falls_back_to_a_flagged_replay(client, monkeypatch, tmp_path):
    from repurpose_api import config

    monkeypatch.setattr(config, "PRECOMPUTE_DIR", tmp_path)
    precompute.save(service.warm(PipelineSettings(dataset_id=DATASET)))
    caching.clear()

    def explode(*a, **k):
        raise RuntimeError("venue laptop fell over")

    monkeypatch.setattr(service, "run_pipeline", explode)

    events = collect(client)
    assert [n for n, _ in events] == ["start", "result"]
    result = events[-1][1]
    assert result["stale"] is True
    assert "venue laptop fell over" in result["staleReason"]
