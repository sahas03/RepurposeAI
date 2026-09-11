"""
The frontend contract.

frontend/src/engine/types.ts is the specification for these responses. The key
lists below are transcribed from it: if this service stops satisfying them, the
UI's promise that "a future backend can return this JSON directly and the UI
needs no changes" quietly stops being true. These tests make that loud instead.
"""

from __future__ import annotations

from .conftest import DATASET

# --- transcribed from frontend/src/engine/types.ts ------------------------
PIPELINE_RESULT_KEYS = {
    "settings",
    "dataset",
    "methodLabel",
    "genesMatched",
    "drugsScored",
    "allScores",
    "candidates",
    "recovery",
    "synthetic",
    "timings",
    "safetyActive",
    "diseaseVec",
    "diseaseGenes",
}
CANDIDATE_KEYS = {
    "drug",
    "reversalScore",
    "rank",
    "knownForDisease",
    "noveltyLabel",
    "safetyScore",
    "reversalScaled",
    "noveltyBonus",
    "finalScore",
    "finalRank",
}
# The six fields types.ts declares...
SETTINGS_KEYS = {
    "datasetId",
    "diseaseName",
    "method",
    "displayTopN",
    "validationTopK",
    "weights",
}
# ...plus one operational field TypeScript ignores. See test_wtcs_variant.py.
SETTINGS_EXTRA = {"wtcsWeighted"}
SYNTHETIC_CHECK_KEYS = {
    "recovered",
    "recoveredCount",
    "plantedTotal",
    "recoveryRate",
    "reinforcingPlanted",
    "reinforcingRanks",
}
RECOVERY_KEYS = {
    "disease",
    "topK",
    "referenceSetSize",
    "recoveredDrugs",
    "recoveredCount",
    "recoveryRate",
    "novelCandidates",
}
GENE_CONTRIBUTION_KEYS = {"gene", "diseaseLogFC", "drugZscore", "contribution", "direction"}


def test_pipeline_result_satisfies_the_typescript_interface(result):
    assert PIPELINE_RESULT_KEYS <= set(result)
    # Extra keys are permitted (TypeScript ignores them), but they must be the
    # documented operational ones, not accidental leakage.
    assert set(result) - PIPELINE_RESULT_KEYS == {"stale", "staleReason", "cached"}


def test_nested_shapes_match(result):
    assert set(result["settings"]) == SETTINGS_KEYS | SETTINGS_EXTRA
    assert set(result["dataset"]) == {"id", "label", "provenance"}
    assert set(result["allScores"][0]) == {"drug", "reversalScore"}
    assert set(result["candidates"][0]) == CANDIDATE_KEYS
    assert set(result["synthetic"]) == SYNTHETIC_CHECK_KEYS


def test_union_typed_fields_use_only_declared_values(result):
    assert result["dataset"]["provenance"] in {"synthetic", "real", "uploaded"}
    assert result["settings"]["method"] in {"cosine", "cosine-fast", "wtcs"}
    for c in result["candidates"]:
        assert c["noveltyLabel"] in {"known hit (validation evidence)", "novel candidate"}


def test_recovery_and_synthetic_are_never_both_populated(result):
    """The two validation checks are distinct and must never be conflated."""
    assert (result["recovery"] is None) != (result["synthetic"] is None)


def test_explain_matches_the_gene_contribution_interface(client):
    r = client.get(f"/api/candidates/planted_reversal_drug_0/explain?datasetId={DATASET}")
    assert r.status_code == 200
    gene = r.json()["topGenes"][0]
    assert set(gene) == GENE_CONTRIBUTION_KEYS
    assert gene["direction"] in {"reversed by drug", "reinforced by drug (unwanted)"}


def test_dataset_descriptor_matches_the_client_interface(client):
    d = client.get("/api/datasets").json()[0]
    assert {"id", "label", "provenance", "disclosure", "diseasePath", "matrixPath"} <= set(d)


def test_disclosure_text_is_served_verbatim(client):
    """The UI shows this string to judges. It must not drift or be softened."""
    d = next(x for x in client.get("/api/datasets").json() if x["id"] == DATASET)
    assert d["disclosure"].startswith(
        "Computer-generated benchmark from scripts/generate_mock_data.py."
    )
    assert "placeholders, not real biology" in d["disclosure"]


def test_response_is_strict_json(client):
    """NaN / Infinity are valid Python but break JSON.parse in the browser."""
    raw = client.post("/api/run", json={"datasetId": DATASET}).text
    for token in ("NaN", "Infinity", "-Infinity"):
        assert token not in raw


def test_docs_example_body_actually_works(client):
    """The example shown in /docs must run, not 404.

    Swagger pre-fills the request body from the schema example. If that example
    is the default "string" placeholder, the first thing anyone tries in the
    docs fails -- which defeats the purpose of shipping them.
    """
    schema = client.get("/openapi.json").json()["components"]["schemas"]["RunRequest"]
    examples = schema.get("examples")
    assert examples, "RunRequest needs an example body for /docs"

    r = client.post("/api/run", json=examples[0])
    assert r.status_code == 200, r.text
    assert r.json()["candidates"], "the documented example must produce a real result"
