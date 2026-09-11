"""
POST /api/run.

The load-bearing test in this file is test_planted_signal_is_recovered: it is
the insurance against pipeline internals changing underneath this service. If
scoring, filtering or fusion in repurposeai/src/ breaks, the API stops
recovering the deliberately planted signal and this fails loudly.
"""

from __future__ import annotations

import math

import pytest

from .conftest import DATASET, PLANTED_REINFORCING, PLANTED_REVERSAL

METHODS = ("cosine", "cosine-fast", "wtcs")


@pytest.mark.parametrize("method", METHODS)
def test_planted_signal_is_recovered(client, method):
    """Every scoring method must rank all three planted reversal compounds on top."""
    r = client.post("/api/run", json={"settings": {"datasetId": DATASET, "method": method}})
    assert r.status_code == 200, r.text
    body = r.json()

    top3 = {c["drug"] for c in body["candidates"][:3]}
    assert top3 == set(PLANTED_REVERSAL), f"{method} lost the planted signal: {top3}"

    synthetic = body["synthetic"]
    assert synthetic["recoveredCount"] == synthetic["plantedTotal"] == 3
    assert synthetic["recoveryRate"] == 1.0


@pytest.mark.parametrize("method", METHODS)
def test_planted_reinforcing_compounds_are_not_promoted(client, method):
    """The deliberately bad compounds must stay out of the shortlist."""
    r = client.post("/api/run", json={"settings": {"datasetId": DATASET, "method": method}})
    shortlist = {c["drug"] for c in r.json()["candidates"]}
    assert shortlist.isdisjoint(PLANTED_REINFORCING)


def test_all_scores_cover_every_compound_ascending(result):
    scores = result["allScores"]
    assert len(scores) == result["drugsScored"] == 150
    values = [s["reversalScore"] for s in scores]
    assert values == sorted(values), "allScores must be ascending (most negative first)"
    assert all(math.isfinite(v) for v in values)


def test_candidate_ranks_are_consistent(result):
    candidates = result["candidates"]
    # finalRank is 1..n in the order returned, sorted by finalScore descending.
    assert [c["finalRank"] for c in candidates] == list(range(1, len(candidates) + 1))
    finals = [c["finalScore"] for c in candidates]
    assert finals == sorted(finals, reverse=True)
    # `rank` is the reversal-order rank and must stay a permutation of 1..n.
    assert sorted(c["rank"] for c in candidates) == list(range(1, len(candidates) + 1))


def test_score_fusion_matches_the_documented_weights(result):
    """finalScore must equal the weighted sum filters.combine_scores() documents."""
    w = result["settings"]["weights"]
    for c in result["candidates"]:
        safety = c["safetyScore"] if c["safetyScore"] is not None else 0.5
        expected = (
            w["reversal"] * c["reversalScaled"]
            + w["safety"] * safety
            + w["novelty"] * c["noveltyBonus"]
        )
        assert c["finalScore"] == pytest.approx(expected, abs=1e-9), c["drug"]


def test_novelty_labelling_is_consistent(result):
    for c in result["candidates"]:
        expected = "known hit (validation evidence)" if c["knownForDisease"] else "novel candidate"
        assert c["noveltyLabel"] == expected
        assert c["noveltyBonus"] == (1.0 if c["knownForDisease"] else 0.6)


def test_safety_screen_reports_standby_without_a_structure_table(result):
    """No smiles_lookup.csv ships with the repo, so the screen must say so honestly."""
    assert result["safetyActive"] is False
    assert all(c["safetyScore"] is None for c in result["candidates"])


def test_disease_vector_is_aligned_and_zscored(result):
    vec, genes = result["diseaseVec"], result["diseaseGenes"]
    assert len(vec) == len(genes) == result["genesMatched"] == 200
    assert genes == sorted(genes), "genes must be in the sorted harmonised order"
    mean = sum(vec) / len(vec)
    assert mean == pytest.approx(0.0, abs=1e-9)
    std = math.sqrt(sum((v - mean) ** 2 for v in vec) / len(vec))
    assert std == pytest.approx(1.0, abs=1e-9), "z-score uses ddof=0, matching the frontend"


def test_pool_size_covers_display_and_validation_needs(client):
    r = client.post(
        "/api/run",
        json={"settings": {"datasetId": DATASET, "displayTopN": 40, "validationTopK": 25}},
    )
    assert len(r.json()["candidates"]) == 40


def test_cosine_and_cosine_fast_are_the_same_computation(client):
    """Both map to signature_matching.score_reversal(method='cosine').

    They are two labels for one vectorised implementation, not two engines --
    identical scores are the point, and only the UI label differs.
    """
    a = client.post("/api/run", json={"settings": {"datasetId": DATASET, "method": "cosine"}}).json()
    b = client.post(
        "/api/run", json={"settings": {"datasetId": DATASET, "method": "cosine-fast"}}
    ).json()

    assert [s["reversalScore"] for s in a["allScores"]] == [
        s["reversalScore"] for s in b["allScores"]
    ]
    assert a["methodLabel"] != b["methodLabel"]


def test_wtcs_is_a_genuinely_different_ranking(client):
    """WTCS is a separate method, not an alias: it must not return cosine's scores."""
    cosine = client.post(
        "/api/run", json={"settings": {"datasetId": DATASET, "method": "cosine"}}
    ).json()
    wtcs = client.post(
        "/api/run", json={"settings": {"datasetId": DATASET, "method": "wtcs"}}
    ).json()
    assert [s["reversalScore"] for s in cosine["allScores"]] != [
        s["reversalScore"] for s in wtcs["allScores"]
    ]
    assert all(-1.0 <= s["reversalScore"] <= 1.0 for s in wtcs["allScores"])


def test_timings_cover_every_stage(result):
    assert set(result["timings"]) == {
        "signature",
        "library",
        "reversal",
        "safety",
        "explain",
        "validation",
    }
    assert all(v >= 0 for v in result["timings"].values())


def test_repeat_runs_hit_the_cache(client):
    first = client.post("/api/run", json={"datasetId": DATASET}).json()
    second = client.post("/api/run", json={"datasetId": DATASET}).json()
    assert first["cached"] is False
    assert second["cached"] is True
    assert first["candidates"] == second["candidates"]

    refreshed = client.post(f"/api/run?refresh=true", json={"datasetId": DATASET}).json()
    assert refreshed["cached"] is False


def test_settings_echo_back_the_resolved_dataset(client):
    r = client.post("/api/run", json={"datasetId": DATASET, "settings": {"method": "wtcs"}})
    settings = r.json()["settings"]
    assert settings["datasetId"] == DATASET
    assert settings["method"] == "wtcs"


def test_defaults_match_the_frontend(client):
    """A bare POST must reproduce the UI's DEFAULT_SETTINGS run.

    Compared field by field against store/useApp.ts's DEFAULT_SETTINGS. The
    backend-only `wtcsWeighted` is checked separately in test_wtcs_variant.py.
    """
    settings = client.post("/api/run", json={}).json()["settings"]
    frontend_defaults = {
        "datasetId": "synthetic-benchmark",
        "diseaseName": "rheumatoid arthritis",
        "method": "cosine-fast",
        "displayTopN": 15,
        "validationTopK": 20,
        "weights": {"reversal": 0.6, "safety": 0.2, "novelty": 0.2},
    }
    assert {k: settings[k] for k in frontend_defaults} == frontend_defaults
    assert set(settings) - set(frontend_defaults) == {"wtcsWeighted"}


def test_tie_ordering_is_deterministic_and_matches_the_frontend(client):
    """Tied scores must come out in drug-matrix column order, every time.

    pandas' sort_values() is an unstable quicksort; JS's Array.sort is stable.
    WTCS zeroes every compound whose up/down enrichments agree in sign (13 of
    150 here), so without pinning this the UI could show tied compounds in a
    different order than the in-browser engine -- and in a different order on
    each run.
    """
    import pandas as pd

    columns = list(
        pd.read_csv("../repurposeai/data/raw/l1000_matrix.csv", index_col=0, nrows=1).columns
    )
    position = {drug: i for i, drug in enumerate(columns)}

    body = client.post(
        "/api/run?refresh=true",
        json={"settings": {"datasetId": DATASET, "method": "wtcs", "wtcsWeighted": False}},
    ).json()
    scores = body["allScores"]

    ties = 0
    for a, b in zip(scores, scores[1:]):
        if a["reversalScore"] == b["reversalScore"]:
            ties += 1
            assert position[a["drug"]] < position[b["drug"]], (
                f"tied compounds {a['drug']} and {b['drug']} are out of column order"
            )
    assert ties > 0, "expected tied WTCS scores in this fixture"


def test_repeated_runs_are_byte_identical(client):
    """Same inputs, same output -- no ordering drift between runs."""
    first = client.post("/api/run?refresh=true", json={"datasetId": DATASET}).text
    second = client.post("/api/run?refresh=true", json={"datasetId": DATASET}).text
    import json as _json

    a, b = _json.loads(first), _json.loads(second)
    for key in ("allScores", "candidates", "synthetic", "diseaseVec", "diseaseGenes"):
        assert a[key] == b[key], key
