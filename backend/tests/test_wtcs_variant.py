"""
The WTCS divergence between the Python pipeline and the frontend's TS port.

Established by running the frontend's own `weightedConnectivityScore` (straight
off the `frontend` branch, unmodified) under Node against the same CSVs:

    Python weighted=True   vs frontend TS : max delta 4.891e-01 over 150 drugs
    Python weighted=False  vs frontend TS : max delta 0.000e+00 over 150 drugs

So the TS function named `weightedConnectivityScore` is a bit-exact port of the
*unweighted* KS score (Lamb et al. 2006) -- the behaviour `weighted=False`
preserves -- and predates the pipeline hardening that made the |z|-weighted
GSEA enrichment (Subramanian et al. 2017) the Python default.

The backend follows the Python default, because the pipeline in src/ is the
single source of truth this service exists to expose. These tests pin both
variants so the divergence cannot be silently lost, and so the day someone
updates the TS port there is a fixture to check it against.

The literal values below were produced by the frontend's TypeScript, not by
this backend. That is the point: they fail if the backend stops being able to
reproduce the frontend's numbers on demand.
"""

from __future__ import annotations

import pytest

from .conftest import DATASET

# From the frontend TS engine (and Python weighted=False), to full precision.
LEGACY_TS_SCORES = {
    "planted_reversal_drug_0": -0.5075000000000001,
    "planted_reversal_drug_1": -0.5075000000000001,
    "planted_reinforcing_drug_3": 0.505,
}


def wtcs(client, weighted: bool) -> dict[str, float]:
    r = client.post(
        "/api/run",
        json={"settings": {"datasetId": DATASET, "method": "wtcs", "wtcsWeighted": weighted}},
    )
    assert r.status_code == 200, r.text
    return {s["drug"]: s["reversalScore"] for s in r.json()["allScores"]}


def test_default_is_the_pipelines_own_weighted_score(client):
    """The backend must follow src/, not the stale TS port."""
    settings = client.post("/api/run", json={"settings": {"method": "wtcs"}}).json()["settings"]
    assert settings["wtcsWeighted"] is True


def test_unweighted_reproduces_the_frontend_engine_exactly(client):
    scores = wtcs(client, weighted=False)
    for drug, expected in LEGACY_TS_SCORES.items():
        assert scores[drug] == pytest.approx(expected, abs=1e-12), drug


def test_weighted_and_unweighted_genuinely_differ(client):
    """Guards against the flag silently becoming a no-op."""
    weighted = wtcs(client, weighted=True)
    unweighted = wtcs(client, weighted=False)
    worst = max(abs(weighted[d] - unweighted[d]) for d in weighted)
    assert worst > 0.1, f"the two WTCS variants should differ substantially, got {worst}"


def test_both_variants_still_recover_the_planted_signal(client):
    """Whichever variant is chosen, the science must still hold up."""
    for weighted in (True, False):
        r = client.post(
            "/api/run",
            json={
                "settings": {
                    "datasetId": DATASET,
                    "method": "wtcs",
                    "wtcsWeighted": weighted,
                }
            },
        ).json()
        top3 = {c["drug"] for c in r["candidates"][:3]}
        assert top3 == {
            "planted_reversal_drug_0",
            "planted_reversal_drug_1",
            "planted_reversal_drug_2",
        }, f"wtcsWeighted={weighted}"


def test_the_flag_does_not_leak_into_cosine(client):
    """signature_matching.score_reversal rejects extra options for cosine."""
    for method in ("cosine", "cosine-fast"):
        r = client.post(
            "/api/run",
            json={"settings": {"method": method, "wtcsWeighted": False}},
        )
        assert r.status_code == 200, r.text


def test_the_variant_is_part_of_the_cache_key(client):
    """Flipping the flag must not return the other variant's cached result."""
    a = wtcs(client, weighted=True)
    b = wtcs(client, weighted=False)
    again = wtcs(client, weighted=True)
    assert a != b
    assert a == again
