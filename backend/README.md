# RepurposeAI — Backend

A thin, rigorous HTTP layer over the verified pipeline in `repurposeai/src/`.

**The one rule this service is built around: there is exactly one scoring engine in
this project, and it lives in `repurposeai/src/`.** This backend imports those modules
directly — it does not reimplement loading, scoring, filtering or validation, and it does
not run a second model. The numbers it returns are produced by the same functions the
Streamlit dashboard and `repurposeai/tests/` exercise.

---

## Quickstart

```bash
pip install -r backend/requirements.txt
cd backend
uvicorn repurpose_api.main:app --reload --port 8000
```

- Interactive docs: <http://localhost:8000/docs>
- Capability check: <http://localhost:8000/api/health>

```bash
curl -X POST http://localhost:8000/api/run \
  -H "Content-Type: application/json" \
  -d '{"datasetId":"synthetic-benchmark"}'
```

A full run over the synthetic benchmark (200 genes × 150 compounds) takes roughly
130 ms end to end, including HTTP.

---

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/datasets` | Dataset descriptors: id, label, provenance, and the disclosure text shown verbatim in the UI. `?includeUnavailable=true` also lists registered datasets whose CSVs aren't present yet. |
| `POST` | `/api/run` | One full pipeline run → `PipelineResult`. Body `{datasetId, settings}`; both optional. `?refresh=true` bypasses the cache. |
| `GET` | `/api/run/stream` | The same run as Server-Sent Events, one event per stage as it completes. |
| `GET` | `/api/candidates/{drug}/explain` | Gene-level rationale for one candidate, plus optional Enrichr pathway enrichment. |
| `GET` | `/api/validate` | Re-runs the recovery check live, so the validation claim can be proven on demand rather than shown as a static slide. |
| `GET` | `/api/health` | Which datasets and optional libraries this instance actually has. |

### The pipeline sequence

`/api/run` mirrors `app/dashboard.py` and `frontend/src/engine/run.ts` stage for stage:

```
load_disease_signature → load_l1000_matrix → harmonize_genes → zscore_disease_signature
  → score_reversal(method=...) → rank_candidates → apply_novelty_filter
  → [apply_safety_filter] → combine_scores → check_recovery / synthetic ground-truth
```

Every call into `src/` goes through `app/pipeline.py`'s `run_stage()`, so one broken
stage returns a structured error naming that stage instead of a raw traceback:

```json
{ "error": { "stage": "reversal scoring", "type": "ValueError",
             "message": "The 'reversal scoring' stage failed: ...", "traceback": null } }
```

Tracebacks are omitted unless `REPURPOSEAI_DEBUG=1`.

---

## Live stage streaming (SSE)

`GET /api/run/stream` emits each stage the moment it genuinely finishes, so the UI's
per-stage sequence is driven by real computation instead of being an animation timed to
look like work.

```
event: start   data: {"settings": {...}, "stages": ["signature", ...]}
event: stage   data: {"id":"signature","ms":41.2,"readout":"200 genes harmonised from 200 rows","index":1,"total":6}
...
event: result  data: {<the same PipelineResult POST /api/run returns>}
```

On failure the stream ends with a `result` event flagged `stale: true` when a precomputed
fallback exists, otherwise an `error` event. Settings arrive as query parameters
(`datasetId`, `method`, `displayTopN`, `validationTopK`, `weightReversal`, …) because
`EventSource` can only issue GET requests.

Measured over real HTTP on the synthetic benchmark: `start` at 12 ms, stage events as each
completes, `result` at 123 ms — genuinely incremental, not one buffered blob.

Two deliberate non-features:

- **No artificial dwell.** A cinematic pace needs a minimum time on screen per stage, but
  that is a presentation decision and belongs in the UI, which already has `dwellMs` for
  it. Padding the server's timings would corrupt the one number here meant to be true.
- **No cache reads.** A cached result has no stages left to happen; replaying its timings
  as live events would misreport what the machine just did. The stream always computes
  fresh, and stores the result so later `POST /api/run` calls stay instant.

**For the frontend:** wire this to the existing `onStage` callback, and call
`EventSource.close()` after `result` or `error` — EventSource reconnects automatically on
a closed connection, which would otherwise start a fresh pipeline run every few seconds.

---

## ⚠ WTCS: the backend and the frontend disagree, on purpose

**Read this before switching the UI to HTTP.** Cosine scores are identical
between the two engines. WTCS scores are not, and the numbers on screen will
change when you swap `localClient` for an HTTP client.

Established by running the frontend's own `weightedConnectivityScore` under Node
against the same CSVs:

| compared against the frontend's TS engine | max delta over 150 compounds |
| --- | --- |
| Python `weighted=True` (the pipeline default) | **0.489** |
| Python `weighted=False` | **0.000** |

So the TS function named `weightedConnectivityScore` is a bit-exact port of the
**unweighted** KS connectivity score (Lamb et al. 2006) — the behaviour the
Python keeps behind `weighted=False`. It predates the pipeline hardening that
made the |z|-weighted GSEA enrichment (Subramanian et al. 2017) the Python
default. The TS port is stale, not wrong-by-design.

**This backend follows the Python default**, because `repurposeai/src/` is the
single source of truth this service exists to expose. Scientifically that is the
right call: the weighted variant is the real WTCS the pitch claims.

Both variants still recover all three planted reversal compounds in the top
three, so the science holds either way — but the scores and the within-top-20
ordering differ visibly.

`settings.wtcsWeighted` (default `true`) selects the variant. Set it to `false`
to reproduce the frontend's current numbers exactly, which is how you diff the
two. It is not part of `types.ts`; the UI ignores it.

**Someone needs to decide:** update the TS port to the weighted score, or accept
the backend's numbers as authoritative once the UI is wired up. Either is
defensible; silently shipping both is the "two scoring engines" problem the
work-split doc warns about.

---

## Frontend contract

Responses mirror `frontend/src/engine/types.ts` **field for field**, camelCase, so the
existing UI needs no changes. `frontend/src/api/client.ts` already defines the seam:

```ts
export const client: RepurposeClient = httpClient(import.meta.env.VITE_API_URL)
```

`POST /api/run` returns exactly the `PipelineResult` interface, plus three operational
fields TypeScript ignores: `cached`, `stale`, `staleReason`.

`tests/test_contract.py` transcribes those interfaces and asserts every response still
satisfies them — if this service drifts from the frontend's types, that test fails rather
than the UI breaking at the venue.

### Proven, not asserted

```bash
cd backend
python scripts/check_frontend_parity.py
```

This extracts the engine `.ts` files from the `frontend` branch at run time (nothing is
vendored, so it cannot drift), runs them under Node over the same CSVs, and compares every
field of `PipelineResult` the UI reads — across all three methods and three pool sizes.

Current result: **198/198 field comparisons match exactly**, including `allScores`
ordering, all ten `Candidate` fields, `diseaseVec`, and both validation blocks. Swapping
`localClient` for an HTTP client changes nothing the UI can observe.

Needs Node ≥22 and `git fetch origin frontend`.

**Three notes for whoever writes `httpClient`:**

1. `loadDataset()` can keep reading the static CSVs client-side exactly as it does today.
   The backend doesn't need to serve them, and `localClient` should stay exported as an
   offline fallback so a dead server never kills the demo.
2. `cosine` and `cosine-fast` are **the same computation**. `signature_matching.py`'s
   cosine path is already vectorised at the source, so there is no separate fast
   implementation to dispatch to — only the UI's method label differs. `wtcs` is a
   genuinely different ranking.
3. `diseaseVec` arrives as a JSON array of numbers; wrap it in `Float64Array` if the
   consuming code wants the typed array the local engine produces.
4. WTCS numbers **will change** unless you pass `wtcsWeighted: false` — see the WTCS
   section above.

---

## What the numbers mean

**Tie ordering is pinned.** pandas' `sort_values()` is an unstable quicksort while JS's
`Array.sort` is stable, so compounds on identical scores could otherwise come out in a
different order than the in-browser engine — and in a different order on each run. WTCS
zeroes every compound whose up/down enrichments agree in sign (13 of 150 on the synthetic
set), so this is not hypothetical. Scores are re-sorted stably over drug-matrix column
order: same values, same set, reproducible order among exact ties.

**Timings are real wall-clock measurements**, not a scripted animation — the six
`timings` keys are the six stage ids in `run.ts`. Two honest consequences:

- The `explain` stage reports ~0 ms because per-candidate decomposition is genuinely
  computed on demand, by `/api/candidates/{drug}/explain`.
- On a **cached dataset**, the `signature` and `library` timings drop to near zero,
  because the loading really didn't happen again. That is the truth about that request,
  not a bug. Use `?refresh=true` for a cold-path measurement.

**The safety screen is on standby.** No `data/raw/smiles_lookup.csv` ships with the repo,
so `safetyActive` is `false` and every `safetyScore` is `null`; score fusion uses
`combine_scores()`'s neutral 0.5 in its place. Drop a `smiles_lookup.csv` (`drug,smiles`)
and an optional `approved_drugs.txt` into `repurposeai/data/raw/` and the Lipinski screen
activates automatically — no code change.

**The two validation checks are never conflated.** `recovery` is real known-drug recovery
against `validate.KNOWN_VALIDATION_SETS`, and is `null` unless the drug library actually
contains real compound names. `synthetic` is the planted-signal sanity check for the mock
matrix. Exactly one of them is populated, and the `/api/validate` statement says plainly
which one you're looking at.

**Pathway enrichment is gated.** Enrichr only recognises real gene symbols, so enrichment
is off by default for the synthetic benchmark's `GENE0000` placeholders and switches on
automatically for real symbols. Every Enrichr call runs with a hard timeout, so no venue
wifi means a gene-level explanation with a note attached — never a hung request. Verified
live against Enrichr with real RA gene symbols (`TNF`, `IL6`, `JAK2`, …), which returns
TNF and IL-17 signalling among the top hits in ~2.5 s.

`pathwaysNote` always says which of the four outcomes happened — skipped, ran and found
nothing, timed out, or unavailable — so the UI never shows a blank panel it cannot
explain.

---

## Demo safety

```bash
cd backend
python scripts/precompute_demo.py --all-methods   # run before you present
python scripts/precompute_demo.py --list
```

`/api/run` always tries a live computation first. Only if that fails does it serve the
stored result, flagged `"stale": true` with a `staleReason` naming what went wrong — so a
failure degrades to a visible replay instead of a crash, and a replay can never be
mistaken for a live run. Disable with `REPURPOSEAI_STALE_FALLBACK=0`.

Results are also memoised in process on `(dataset files, settings)`, so repeat runs of
your demo configuration are instant. Editing a CSV changes its fingerprint and
invalidates the cache automatically.

---

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `REPURPOSEAI_CORS_ORIGINS` | localhost 5173/4173/3000 | Comma-separated origins. `*` is accepted for an unknown demo machine. |
| `REPURPOSEAI_DATA_DIR` | `repurposeai/data/raw` | Where the CSVs live. |
| `REPURPOSEAI_DEBUG` | `0` | Include tracebacks in error responses. |
| `REPURPOSEAI_STALE_FALLBACK` | `1` | Serve a flagged precomputed result when a live run fails. |
| `REPURPOSEAI_CACHE_SIZE` | `32` | Max cached results. |
| `REPURPOSEAI_ENRICHR_TIMEOUT` | `6` | Seconds before giving up on Enrichr. |
| `REPURPOSEAI_PRECOMPUTE_DIR` | `backend/precomputed` | Fallback store. |

---

## Tests

```bash
cd backend
python -m pytest tests -q
```

69 tests, ~3 s. The load-bearing one is `test_planted_signal_is_recovered`: for **every**
scoring method, the three deliberately planted reversal compounds must come back as the
top three candidates, and the two planted reinforcing compounds must stay out of the
shortlist. That is the insurance against pipeline internals changing underneath this
service — if scoring, filtering or fusion breaks in `src/`, these fail loudly instead of
the demo failing quietly.

The suite also asserts the frontend contract, that `finalScore` equals the documented
weighted sum, that the z-score uses `ddof=0` (matching the frontend), that responses
contain no `NaN`/`Infinity` tokens (which would break `JSON.parse`), that the SSE stream
reports every stage in pipeline order with a result identical to `POST /api/run`, and that
a failed run falls back to a flagged replay.

Enrichment tests drive the wrapper with a stub rather than the network — a suite that needs
venue wifi is worthless at a venue with no wifi. One of them caught a real defect worth
knowing about: wrapping the call in a `ThreadPoolExecutor` context manager silently undoes
the timeout, because `shutdown(wait=True)` on exit blocks until the worker finishes. The
same pattern is still present in `repurposeai/app/dashboard.py::_try_pathway_enrichment`,
where a hung Enrichr call will stall the dashboard for as long as Enrichr takes — worth
fixing there too, but that file belongs to Phase 5 so this backend leaves it alone.

---

## Docker

```bash
docker build -f backend/Dockerfile -t repurposeai-api .   # from the REPOSITORY ROOT
docker run --rm -p 8000:8000 repurposeai-api
```

The build context is the repo root because the image needs both this service and the
pipeline package it imports.

---

## Deliberately out of scope

No PostgreSQL, no Celery, no auth/users/JWT, no websocket notification system. A
stateless single-audience pipeline API needs none of it, and that category of complexity
is exactly why the previously deleted `backend/` (commit `94d2e9a`, removed in `ae84327`)
was the wrong artifact to resume from — it ran its own separate scikit-learn model
alongside the real pipeline, which is the "two scoring engines, only one can be presented"
problem the team's work-split doc warns about.

SQLite would be the ceiling for any persistence here, and even that isn't needed yet:
caching is in-process and the precompute store is plain JSON files.

## Adding real data

`real-lincs` is already registered in `repurpose_api/datasets.py` and reports
`available: false` until the files exist. Drop `disease_signature_real.csv` and
`l1000_matrix_real.csv` into `repurposeai/data/raw/` — in the same schema
`data_loader.py` already expects — and it appears in `/api/datasets` with no code change.
Pathway enrichment then switches on by itself, because the gene identifiers become real
symbols.
