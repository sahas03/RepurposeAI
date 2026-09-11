"""Explain, validate, health, dataset listing, error handling and demo fallback."""

from __future__ import annotations

import pytest

from repurpose_api import caching, precompute, service
from repurpose_api.schemas import PipelineSettings

from .conftest import DATASET, PLANTED_REVERSAL


# --- GET /api/datasets, /api/health --------------------------------------
def test_datasets_lists_only_available_data(client):
    ids = [d["id"] for d in client.get("/api/datasets").json()]
    assert ids == [DATASET]


def test_unavailable_datasets_are_visible_but_flagged(client):
    everything = client.get("/api/datasets?includeUnavailable=true").json()
    real = next(d for d in everything if d["id"] == "real-lincs")
    assert real["available"] is False
    assert real["provenance"] == "real"


def test_health_reports_capabilities(client):
    body = client.get("/api/health").json()
    assert body["status"] == "ok"
    assert DATASET in body["datasets"]
    assert set(body["capabilities"]) == {
        "rdkitAvailable",
        "gseapyAvailable",
        "safetyTableLoaded",
        "staleFallbackEnabled",
    }


# --- GET /api/candidates/{drug}/explain ----------------------------------
def test_explain_decomposes_a_planted_candidate(client):
    r = client.get(f"/api/candidates/{PLANTED_REVERSAL[0]}/explain?topNGenes=8")
    assert r.status_code == 200
    body = r.json()

    assert body["drug"] == PLANTED_REVERSAL[0]
    assert len(body["topGenes"]) == 8
    # A planted reversal compound mirrors the signature, so every top
    # contribution should be a reversal, not a reinforcement.
    assert all(g["direction"] == "reversed by drug" for g in body["topGenes"])
    assert body["reversedCount"] == 8

    contributions = [g["contribution"] for g in body["topGenes"]]
    assert contributions == sorted(contributions), "most negative contribution first"
    for g in body["topGenes"]:
        assert g["contribution"] == pytest.approx(g["diseaseLogFC"] * g["drugZscore"], rel=1e-9)


def test_explain_flags_a_reinforcing_compound(client):
    body = client.get("/api/candidates/planted_reinforcing_drug_3/explain").json()
    assert all(g["direction"] == "reinforced by drug (unwanted)" for g in body["topGenes"])
    assert body["reversedCount"] == 0


def test_pathway_enrichment_is_gated_off_for_placeholder_genes(client):
    """Enrichr only recognises real symbols; GENE0000 placeholders must not be sent."""
    body = client.get(f"/api/candidates/{PLANTED_REVERSAL[0]}/explain").json()
    assert body["pathways"] is None
    assert "placeholder gene identifiers" in body["pathwaysNote"]


def test_unknown_drug_is_a_clean_404(client):
    r = client.get("/api/candidates/not-a-compound/explain")
    assert r.status_code == 404
    error = r.json()["error"]
    assert error["type"] == "DrugNotFound"
    assert "150 compounds available" in error["message"]
    assert error["traceback"] is None


# --- GET /api/validate ----------------------------------------------------
def test_validate_reports_the_synthetic_check_honestly(client):
    body = client.get(f"/api/validate?datasetId={DATASET}&topK=20").json()
    assert body["recovery"] is None
    assert body["synthetic"]["recoveredCount"] == 3
    # The statement must not imply real drugs were recovered.
    assert "not a real-drug result" in body["statement"]
    assert "placeholder identifiers, not drug names" in body["statement"]


def test_validate_honours_top_k(client):
    body = client.get(f"/api/validate?datasetId={DATASET}&topK=3").json()
    assert body["topK"] == 3
    assert body["synthetic"]["recoveredCount"] == 3


def test_validate_on_an_unknown_disease_makes_no_claim(client):
    body = client.get(f"/api/validate?datasetId={DATASET}&diseaseName=psoriasis").json()
    assert body["recovery"] is None
    assert body["synthetic"] is not None


# --- errors ---------------------------------------------------------------
def test_unknown_dataset_is_a_clean_404(client):
    r = client.post("/api/run", json={"datasetId": "no-such-dataset"})
    assert r.status_code == 404
    assert "Unknown dataset" in r.json()["error"]["message"]


def test_registered_but_missing_dataset_says_what_is_missing(client):
    r = client.post("/api/run", json={"datasetId": "real-lincs"})
    assert r.status_code == 404
    assert "data files are not present yet" in r.json()["error"]["message"]


def test_invalid_method_is_rejected_before_any_work(client):
    assert client.post("/api/run", json={"settings": {"method": "sorcery"}}).status_code == 422


def test_stage_failure_returns_a_structured_error(client, monkeypatch):
    """A broken stage names the stage instead of leaking a traceback."""
    from repurpose_api import bridge

    def explode(*a, **k):
        raise bridge.StageError("reversal scoring", ValueError("matrix is not numeric"))

    monkeypatch.setattr(service, "run_pipeline", explode)
    monkeypatch.setattr(precompute, "fallback", lambda *a, **k: None)
    caching.clear()

    r = client.post("/api/run", json={"datasetId": DATASET})
    assert r.status_code == 500
    error = r.json()["error"]
    assert error["stage"] == "reversal scoring"
    assert "matrix is not numeric" in error["message"]
    assert error["traceback"] is None, "tracebacks stay hidden unless REPURPOSEAI_DEBUG=1"


# --- demo-safety fallback --------------------------------------------------
def test_failed_run_falls_back_to_the_precomputed_result(client, monkeypatch, tmp_path):
    """A live failure degrades to a flagged replay, never to a crash."""
    from repurpose_api import config

    monkeypatch.setattr(config, "PRECOMPUTE_DIR", tmp_path)
    settings = PipelineSettings(dataset_id=DATASET)
    precompute.save(service.warm(settings))
    caching.clear()

    def explode(*a, **k):
        raise RuntimeError("venue laptop ran out of memory")

    monkeypatch.setattr(service, "run_pipeline", explode)

    body = client.post("/api/run", json={"datasetId": DATASET}).json()
    assert body["stale"] is True
    assert "venue laptop ran out of memory" in body["staleReason"]
    # A replay is still a real, complete result -- just an older one.
    assert {c["drug"] for c in body["candidates"][:3]} == set(PLANTED_REVERSAL)


def test_fresh_results_are_never_marked_stale(result):
    assert result["stale"] is False
    assert result["staleReason"] is None


def test_fallback_is_skipped_when_disabled(client, monkeypatch, tmp_path):
    from repurpose_api import config

    monkeypatch.setattr(config, "PRECOMPUTE_DIR", tmp_path)
    precompute.save(service.warm(PipelineSettings(dataset_id=DATASET)))
    monkeypatch.setattr(config, "STALE_FALLBACK_ENABLED", False)
    caching.clear()

    def explode(*a, **k):
        raise RuntimeError("nope")

    monkeypatch.setattr(service, "run_pipeline", explode)
    assert client.post("/api/run", json={"datasetId": DATASET}).status_code == 500


# --- pathway enrichment ----------------------------------------------------
# Enrichr is a live third-party service, so these drive the wrapper with a stub
# rather than the network: a test suite that needs venue wifi is worthless at a
# venue with no wifi. The real Enrichr call was verified separately by hand.
def test_pathway_results_are_mapped_to_the_response_shape(client, monkeypatch):
    import pandas as pd

    from repurpose_api import bridge, explain as explain_mod

    fake = pd.DataFrame(
        {
            "Term": ["TNF signaling pathway", "IL-17 signaling pathway"],
            "Overlap": ["4/112", "3/94"],
            "Adjusted P-value": [1.77e-11, 1.18e-11],
            "Genes": ["TNF;IL6;CXCL10;MMP9", "IL6;IL1B;CCL2"],
        }
    )
    monkeypatch.setattr(bridge, "GSEAPY_AVAILABLE", True)
    monkeypatch.setattr(explain_mod.bridge, "pathway_enrichment", lambda genes, gene_sets: fake)

    body = client.get(
        f"/api/candidates/{PLANTED_REVERSAL[0]}/explain?runPathways=true"
    ).json()
    assert body["pathwaysNote"] is None
    assert [p["term"] for p in body["pathways"]] == [
        "TNF signaling pathway",
        "IL-17 signaling pathway",
    ]
    assert body["pathways"][0]["adjustedPValue"] == pytest.approx(1.77e-11)


def test_empty_enrichment_is_reported_not_left_blank(client, monkeypatch):
    import pandas as pd

    from repurpose_api import bridge, explain as explain_mod

    monkeypatch.setattr(bridge, "GSEAPY_AVAILABLE", True)
    monkeypatch.setattr(
        explain_mod.bridge, "pathway_enrichment", lambda genes, gene_sets: pd.DataFrame()
    )

    body = client.get(f"/api/candidates/{PLANTED_REVERSAL[0]}/explain?runPathways=true").json()
    assert body["pathways"] is None
    assert "returned no enriched pathways" in body["pathwaysNote"]


def test_enrichment_failure_never_fails_the_request(client, monkeypatch):
    from repurpose_api import bridge, explain as explain_mod

    def boom(genes, gene_sets):
        raise ConnectionError("no route to host")

    monkeypatch.setattr(bridge, "GSEAPY_AVAILABLE", True)
    monkeypatch.setattr(explain_mod.bridge, "pathway_enrichment", boom)

    r = client.get(f"/api/candidates/{PLANTED_REVERSAL[0]}/explain?runPathways=true")
    assert r.status_code == 200, "a dead Enrichr must not take down the explanation"
    body = r.json()
    assert body["pathways"] is None
    assert "no route to host" in body["pathwaysNote"]
    assert len(body["topGenes"]) == 10, "gene-level explanation still returned in full"


def test_enrichment_times_out_without_hanging(client, monkeypatch):
    import time

    from repurpose_api import bridge, config, explain as explain_mod

    monkeypatch.setattr(bridge, "GSEAPY_AVAILABLE", True)
    monkeypatch.setattr(config, "ENRICHR_TIMEOUT", 1)
    monkeypatch.setattr(
        explain_mod.bridge, "pathway_enrichment", lambda genes, gene_sets: time.sleep(30)
    )

    started = time.perf_counter()
    body = client.get(f"/api/candidates/{PLANTED_REVERSAL[0]}/explain?runPathways=true").json()
    assert time.perf_counter() - started < 10, "the timeout must actually bound the request"
    assert body["pathways"] is None
    assert "timed out" in body["pathwaysNote"]
