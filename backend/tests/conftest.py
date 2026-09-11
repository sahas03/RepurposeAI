"""Shared fixtures. Every test runs against the real synthetic CSVs in data/raw."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from repurpose_api import caching  # noqa: E402
from repurpose_api.main import app  # noqa: E402

DATASET = "synthetic-benchmark"

#: scripts/generate_mock_data.py plants these, and tests/test_pipeline.py in the
#: main package relies on the same naming convention.
PLANTED_REVERSAL = (
    "planted_reversal_drug_0",
    "planted_reversal_drug_1",
    "planted_reversal_drug_2",
)
PLANTED_REINFORCING = ("planted_reinforcing_drug_3", "planted_reinforcing_drug_4")


@pytest.fixture()
def client() -> TestClient:
    # A cold cache per test, so a cached result can never mask a broken run.
    caching.clear()
    # raise_server_exceptions=False so tests see the HTTP response a browser
    # would get, rather than the exception being re-raised into the test.
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture()
def result(client: TestClient) -> dict:
    r = client.post("/api/run", json={"datasetId": DATASET})
    assert r.status_code == 200, r.text
    return r.json()
