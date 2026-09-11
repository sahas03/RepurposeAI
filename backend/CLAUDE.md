# CLAUDE.md — backend/

FastAPI service that exposes `repurposeai/src/*.py` over HTTP. Read
`backend/README.md` for full depth (endpoint reference, request/response
examples, config vars); this file is the fast orientation pass — what makes
this directory tick, and the mistakes already made once that don't need
repeating.

Read this file before touching anything under `backend/`.

---

## The rule that matters most: one scoring engine

**Every number this service returns comes from `repurposeai/src/*.py`.** Not a
port, not a reimplementation, not a second model — `repurpose_api/bridge.py`
puts `repurposeai/src` and `repurposeai/app` on `sys.path` and imports the real
functions. If you're about to write scoring, filtering, harmonisation, or
validation logic in `backend/`, stop — that logic already exists in `src/`
and belongs there, not here.

This is not a style preference. A full FastAPI/PostgreSQL/Celery backend with
its own scikit-learn model was built, then deleted from `main` (commit
`94d2e9a`, removed by `ae84327`), specifically because it ran a second scoring
engine alongside the real pipeline — "two scoring engines, only one can be
presented" is the failure mode the team's own work-split doc warns about. Do
not reintroduce it.

**The `frontend` branch's root `CLAUDE.md` describes that deleted backend**
(Postgres, Celery, JWT, async job polling) as if it still exists. It doesn't.
It was never rewritten after the backend was removed and this one was built in
its place. Don't trust it for anything backend-related — trust this file and
`backend/README.md` instead.

---

## Commands

```bash
cd backend
python scripts/serve.py                  # start the API (see gotcha below re: uvicorn directly)
python -m pytest tests -q                 # 70 tests, ~3s
python scripts/check_frontend_parity.py   # numeric proof vs the frontend's own TS engine
python scripts/precompute_demo.py --all-methods   # refresh the demo-safety fallback
```

No build step, no linter configured yet. Tests are the verification loop —
run them before claiming a change works, not just a manual curl.

---

## Layout

```
repurpose_api/
  bridge.py         the ONLY import seam into repurposeai/src -- everything else calls through here
  datasets.py        dataset registry + harmonised loading, cached on file identity
  orchestrator.py    one pipeline run, stage by stage, mirrors app/dashboard.py's sequence
  service.py         cache lookup + demo-safety fallback, sits in front of the orchestrator
  streaming.py        SSE version of the orchestrator run
  explain.py          gene-level rationale + gated Enrichr pathway enrichment
  caching.py / precompute.py   in-process memoisation / on-disk demo fallback
  schemas.py          response models -- mirrors frontend/src/engine/types.ts field-for-field
  main.py             FastAPI app, CORS, structured error handlers
  routers/            one file per endpoint group
scripts/
  serve.py                    start the API (dual loopback bind, see below)
  check_frontend_parity.py    runs the frontend's TS engine under Node, diffs it against this API
  precompute_demo.py          refresh backend/precomputed/ (the stale-fallback store)
tests/                70 tests: contract, run, streaming, endpoints, the WTCS divergence
```

---

## Known gotchas (hit once already, don't re-discover)

**WTCS scores diverge from the frontend, on purpose.** The frontend's
`weightedConnectivityScore` in `frontend/src/engine/scoring.ts` is a bit-exact
port of the *unweighted* KS connectivity score (Lamb 2006). The Python default
in `signature_matching.py` is now the |z|-weighted GSEA enrichment
(Subramanian 2017), after a pipeline-hardening commit the TS port predates.
Max delta over 150 compounds: **0.489**. `settings.wtcsWeighted` (default
`true`) selects the variant; set it `false` to reproduce the frontend's
current numbers exactly. This is not a bug to fix quietly — read the WTCS
section of `backend/README.md` before changing either side's behaviour, and
tell whoever owns `frontend` before flipping the default.

**`localhost` may not resolve the way you expect on Windows.** It often means
`::1` (IPv6), while `uvicorn --host 127.0.0.1` binds IPv4 only — the server
reports itself healthy, the log stays empty, and the browser just times out.
Use `python scripts/serve.py`, which binds both loopback families in one
process. Don't hand-roll a `uvicorn` invocation unless you mean to.

**pandas' `sort_values()` is an unstable quicksort; the frontend's
`Array.sort` is stable.** WTCS zeroes ~13 of 150 compounds (identical
enrichment sign), so without pinning the tie order it can differ from the
frontend's -- and differ between runs of this service. `orchestrator.py`
re-sorts stably over drug-matrix column order before returning `allScores`.
If you touch that sort, keep it stable and keep the ordering test in
`test_run.py` green.

**The result cache key must cover every input the run depends on**, not just
the dataset CSVs -- it also fingerprints the optional
`smiles_lookup.csv`/`approved_drugs.txt`, so dropping a structure table onto
a running server doesn't keep serving pre-safety cached results. If you add a
new optional input file, fold it into `caching.result_key()`.

**The SSE endpoint never reads the cache.** A cached result has no stages
left to report; replaying its timings as live events would misreport what the
machine just did. `service.run(..., on_stage=...)` forces a live computation
whenever a stage callback is passed -- don't "fix" that as if it were a missed
cache-hit optimisation.

---

## Verifying a change actually works

Three checks, in order of how much they prove:

1. `python -m pytest tests -q` -- fast, catches regressions in isolation.
2. `python scripts/check_frontend_parity.py` -- extracts the frontend's TS
   engine from `origin/frontend` at run time (nothing vendored, can't drift)
   and diffs every field of `PipelineResult` against this API's output, across
   all three methods. 198/198 should match (WTCS compared at
   `wtcsWeighted=false`, see the gotcha above).
3. A real HTTP call -- `python scripts/serve.py`, then hit `/docs` or
   `curl -X POST localhost:8000/api/run -d '{"datasetId":"synthetic-benchmark"}'`.
   The test client can mask things a real server won't (see: the
   `ThreadPoolExecutor` timeout bug in `explain.py`'s history, or the docs
   example that 404'd on Swagger's `"string"` placeholder until
   `schemas.RunRequest` got a real example).

The load-bearing test is `test_run.py::test_planted_signal_is_recovered`: for
every scoring method, the three planted reversal compounds must rank top-3.
If that fails, something in `repurposeai/src/` changed underneath this
service -- go look there, not here.

---

## Repository state (as of the `backend` branch)

- `main` -- `repurposeai/` only; the deleted-backend commits are in history
  but reverted.
- `backend` (this branch) -- `main` + `backend/`. Local commits only, **not
  pushed**. `repurposeai/` is untouched by every commit on this branch
  (`git diff main -- repurposeai/` is empty) -- keep it that way.
- `frontend` -- unmerged, unrelated history, everything under `frontend/`.
  Its root `CLAUDE.md` is stale re: the backend (see the rule above). Its
  `frontend/CLAUDE.md` (the React/engine one) is accurate and worth reading if
  you're touching the client integration.

No `backend/CLAUDE.md`-equivalent existed before this file. If `main` and
`backend` merge, this file should merge with them; if `frontend` ever merges
too, the stale root `CLAUDE.md` needs rewriting to describe this backend
instead of the deleted one.
