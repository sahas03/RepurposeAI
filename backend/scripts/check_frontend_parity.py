"""
check_frontend_parity.py
Prove the backend returns exactly what the frontend's own engine computes.

The strongest available evidence that swapping `localClient` for an HTTP client
changes nothing the UI can observe: run the TypeScript engine straight off the
`frontend` branch under Node, over the same CSVs, and compare every field of
PipelineResult that the UI reads.

Nothing is vendored. The .ts files are extracted from git at run time, so this
check can never drift from what the frontend branch actually contains -- and it
starts failing the moment either side changes behaviour.

    cd backend
    python scripts/check_frontend_parity.py            # all methods
    python scripts/check_frontend_parity.py --verbose  # per-check output

Requires Node (>=22, for native TypeScript type-stripping) and a git checkout
with the `frontend` branch fetched. Exits non-zero on any mismatch.

Known, deliberate divergence: the frontend's `weightedConnectivityScore` is a
bit-exact port of the UNWEIGHTED KS score (Lamb et al. 2006), which the Python
keeps behind `weighted=False`, while the pipeline's default is now the
|z|-weighted GSEA enrichment (Subramanian et al. 2017). So WTCS is compared
with `wtcsWeighted: false`. See the WTCS section of backend/README.md.
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
REPO = BACKEND.parent
sys.path.insert(0, str(BACKEND))

logging.disable(logging.INFO)

ENGINE_MODULES = ("types", "loader", "scoring", "filters", "validate")
ENGINE_BRANCH = "origin/frontend"
ENGINE_PATH = "frontend/src/engine"

HARNESS = """
import { readFileSync } from 'node:fs'
import { buildCandidates } from './filters.ts'
import { harmonize, parseDiseaseSignature, parseL1000Matrix } from './loader.ts'
import { cosineReversalScore, weightedConnectivityScore, zscoreDiseaseSignature } from './scoring.ts'
import { checkRecovery, hasRealValidationSignal, knownDrugSet, syntheticGroundTruth } from './validate.ts'

const [diseasePath, matrixPath, method, displayTopN, validationTopK] = process.argv.slice(2)
const dataset = harmonize(
  parseDiseaseSignature(readFileSync(diseasePath, 'utf8')),
  parseL1000Matrix(readFileSync(matrixPath, 'utf8')),
  { id: 'synthetic-benchmark', label: 'Synthetic Benchmark', provenance: 'synthetic' },
)
const settings = {
  datasetId: 'synthetic-benchmark',
  diseaseName: 'rheumatoid arthritis',
  method,
  displayTopN: Number(displayTopN),
  validationTopK: Number(validationTopK),
  weights: { reversal: 0.6, safety: 0.2, novelty: 0.2 },
}
const diseaseVec = zscoreDiseaseSignature(dataset.disease.map((d) => d.logFC))
const allScores =
  settings.method === 'wtcs'
    ? weightedConnectivityScore(dataset)
    : cosineReversalScore(dataset, diseaseVec, settings.method === 'cosine-fast')
const known = knownDrugSet(settings.diseaseName)
const poolN = Math.max(settings.displayTopN, settings.validationTopK, 20)
const candidates = buildCandidates(allScores, poolN, known, settings, null)
const realSignal = hasRealValidationSignal(dataset.drugs, known)
process.stdout.write(JSON.stringify({
  genesMatched: dataset.genes.length,
  drugsScored: dataset.drugs.length,
  allScores,
  candidates,
  recovery: realSignal ? checkRecovery(candidates, settings.diseaseName, settings.validationTopK) : null,
  synthetic: realSignal ? null : syntheticGroundTruth(candidates, dataset.drugs, settings.validationTopK),
  diseaseVec: Array.from(diseaseVec),
  diseaseGenes: dataset.genes,
}))
"""

CANDIDATE_FIELDS = (
    "drug", "reversalScore", "rank", "knownForDisease", "noveltyLabel",
    "safetyScore", "reversalScaled", "noveltyBonus", "finalScore", "finalRank",
)
CASES = ((15, 20), (150, 20), (5, 3))
TOL = 1e-9


def close(a, b) -> bool:
    if isinstance(a, bool) or isinstance(b, bool):
        return a == b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return abs(a - b) <= TOL * max(1.0, abs(a), abs(b))
    return a == b


def deep_close(a, b) -> bool:
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(deep_close(x, y) for x, y in zip(a, b))
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(deep_close(a[k], b[k]) for k in a)
    return close(a, b)


def extract_engine(workdir: Path) -> None:
    for module in ENGINE_MODULES:
        blob = subprocess.run(
            ["git", "show", f"{ENGINE_BRANCH}:{ENGINE_PATH}/{module}.ts"],
            cwd=REPO, capture_output=True, text=True,
        )
        if blob.returncode != 0:
            raise SystemExit(
                f"Could not read {module}.ts from {ENGINE_BRANCH}.\n{blob.stderr}\n"
                "Fetch the frontend branch first: git fetch origin frontend"
            )
        (workdir / f"{module}.ts").write_text(blob.stdout, encoding="utf-8")
    (workdir / "harness.ts").write_text(HARNESS, encoding="utf-8")


def run_ts(workdir: Path, disease: Path, matrix: Path, method: str, top_n: int, top_k: int) -> dict:
    out = subprocess.run(
        ["node", "harness.ts", str(disease), str(matrix), method, str(top_n), str(top_k)],
        cwd=workdir, capture_output=True, text=True, shell=(sys.platform == "win32"),
    )
    if out.returncode != 0:
        raise SystemExit(f"The frontend engine failed to run under Node:\n{out.stderr}")
    return json.loads(out.stdout)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--verbose", action="store_true", help="Print every individual check.")
    args = ap.parse_args()

    if shutil.which("node") is None:
        raise SystemExit("Node is not installed; this check needs it to run the frontend engine.")

    from fastapi.testclient import TestClient  # noqa: PLC0415

    from repurpose_api.datasets import get_spec  # noqa: PLC0415
    from repurpose_api.main import app  # noqa: PLC0415

    spec = get_spec("synthetic-benchmark")
    client = TestClient(app, raise_server_exceptions=False)
    failures: list[str] = []
    checks = 0

    # A short temp path: Windows cannot run native binaries from a deeply
    # nested working directory.
    workdir = Path(tempfile.mkdtemp(prefix="parity-"))
    try:
        extract_engine(workdir)

        for method in ("cosine", "cosine-fast", "wtcs"):
            for top_n, top_k in CASES:
                tag = f"{method}/{top_n}/{top_k}"
                ts = run_ts(workdir, spec.disease_path, spec.matrix_path, method, top_n, top_k)
                response = client.post("/api/run?refresh=true", json={"settings": {
                    "datasetId": "synthetic-benchmark",
                    "diseaseName": "rheumatoid arthritis",
                    "method": method,
                    "displayTopN": top_n,
                    "validationTopK": top_k,
                    "weights": {"reversal": 0.6, "safety": 0.2, "novelty": 0.2},
                    # The TS port computes the unweighted KS variant.
                    "wtcsWeighted": False,
                }})
                assert response.status_code == 200, response.text
                be = response.json()

                probes = [
                    ("genesMatched", ts["genesMatched"], be["genesMatched"]),
                    ("drugsScored", ts["drugsScored"], be["drugsScored"]),
                    ("diseaseGenes", ts["diseaseGenes"], be["diseaseGenes"]),
                    ("diseaseVec", ts["diseaseVec"], be["diseaseVec"]),
                    ("allScores", ts["allScores"], be["allScores"]),
                    ("recovery", ts["recovery"], be["recovery"]),
                ]
                for field in CANDIDATE_FIELDS:
                    probes.append((
                        f"candidates.{field}",
                        [c[field] for c in ts["candidates"]],
                        [c[field] for c in be["candidates"]],
                    ))
                if ts["synthetic"] is None or be["synthetic"] is None:
                    probes.append(("synthetic", ts["synthetic"], be["synthetic"]))
                else:
                    for key in ts["synthetic"]:
                        probes.append((f"synthetic.{key}", ts["synthetic"][key], be["synthetic"][key]))

                for name, expected, actual in probes:
                    checks += 1
                    ok = deep_close(expected, actual)
                    if args.verbose:
                        print(f"  {'PASS' if ok else 'FAIL'}  [{tag}] {name}")
                    if not ok:
                        failures.append(f"[{tag}] {name}")
                if not args.verbose:
                    status = "ok" if not failures else "MISMATCH"
                    print(f"  {tag:24s} {len(probes):3d} fields  {status}")
    finally:
        shutil.rmtree(workdir, ignore_errors=True)

    print()
    if failures:
        print(f"{len(failures)} of {checks} field comparisons DIFFER from the frontend engine:")
        for f in failures:
            print("  -", f)
        return 1
    print(f"All {checks} field comparisons match the frontend engine exactly.")
    print("Swapping localClient for an HTTP client changes nothing the UI can observe.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
