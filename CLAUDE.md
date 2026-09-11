# CLAUDE.md — RepurposeAI (whole project)

AI-assisted computational drug repurposing, target disease **rheumatoid
arthritis**. Built for CBIT National Level Ideathon 5.0.

This file covers the repository as a whole. `frontend/CLAUDE.md` covers the
frontend in depth; `backend/README.md` and `backend/docs/API_CONTRACT.md` cover
the service. Read this one first — it explains how the three parts relate, which
is the part no single subfolder tells you.

```
repurposeai/   original hackathon pipeline — Python + Streamlit
backend/       FastAPI service — Postgres, Celery/Redis, JWT/RBAC, its own AI pipeline
frontend/      React/Vite UI — currently runs a TS port of repurposeai/ in-browser
```

---

## Read this before doing integration work

**There are two independent drug-repurposing implementations in this repo, and
they are not the same pipeline.**

| | `repurposeai/src/*.py` | `backend/app/ai/` |
|---|---|---|
| Method | cosine reversal + WTCS over an L1000-style matrix | similarity / ranking / explainability models (scikit-learn) |
| Data | two CSVs in `repurposeai/data/raw/` | 17-table Postgres schema, seeded |
| Interface | imported directly by the Streamlit app | behind `POST /repurposing/run` |
| Status | the hackathon deliverable | production-structured service |

**The frontend currently mirrors the first one.** `frontend/src/engine/` is a
line-for-line TypeScript port of `repurposeai/src/*.py`, running in the browser
against the same CSVs.

So "integrate the frontend and backend" is not a wiring job. The first question
is *which pipeline the UI should render*, because that decides whether the
adapter is a thin translation or a genuine reconciliation of two different
scoring methods with different output shapes. Do not start writing `httpClient`
before that is settled — and do not silently reshape one side's semantics to fit
the other's UI.

### The seam

Frontend: `frontend/src/api/client.ts` is the only place that knows where
computation happens. Implement `RepurposeClient` and swap the final export.
Response shapes are in `frontend/src/engine/types.ts`.

Backend: the repurposing flow is **asynchronous**, three calls —

```
POST /repurposing/run          -> 202, returns a job
GET  /repurposing/{job_id}     -> poll status
GET  /repurposing/{job_id}/results -> ranked, explained predictions
```

Requires JWT auth with the `repurposing:run` and `prediction:read` permissions.
`CORS_ORIGINS` in `backend/.env.example` already allows `http://localhost:5173`.

**Known impedance mismatch:** the frontend's `run()` takes an `onStage` callback
and expects six named stages to report in sequence — that is what drives the
discovery sequence animation. The backend returns a job to poll. The backend does
have native WebSockets with a Redis pub/sub relay, which is the natural way to
feed `onStage` properly; polling would work but would flatten the sequence into
a spinner, which is precisely what that UI exists to avoid.

---

## Scientific honesty — a project-wide rule, not a frontend one

Both halves already commit to this independently, and it must stay that way.

- The backend seeds `DEMO/SYNTHETIC DATA` in every row's metadata. Drug, gene and
  disease *names* are real public terms; the *relationships* between them are
  synthetic and are not from any curated biomedical database.
- The frontend computes every displayed number live and labels its provenance on
  every surface via `<Provenance>`. `frontend/src/components/sections/Footer.tsx`
  holds the canonical "what is real vs a stand-in" ledger.
- Inactive subsystems are shown as inactive, never as passing. The frontend's
  Lipinski screen genuinely cannot run without structure descriptors and says so.
- Nothing in this system is a clinical or diagnostic claim. Predictions are
  computational and require experimental validation.

**Never hardcode a score, count or example drug name into UI code**, and never
merge the two distinct validation checks (`checkRecovery` needs real drug names;
`syntheticGroundTruth` tests ranking math on planted signals). A judge who spots
one invented number discounts all of them.

---

## Repository state

Two branches, deliberately unmerged:

- `main` — `backend/` + `repurposeai/`
- `frontend` — everything under `frontend/`

They have **zero overlapping paths**, so the merge is conflict-free. Histories
are unrelated (the frontend began as a standalone repo), so merging needs
`--allow-unrelated-histories`. The frontend was moved into `frontend/` precisely
to match the existing `backend/` convention and remove the `.gitignore` /
`.claude/launch.json` collisions a root-level merge would have hit.

---

## Running each part

```bash
# frontend
cd frontend && npm install && npm run dev        # :5173, no backend needed

# backend  (needs Postgres + Redis)
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
alembic upgrade head && python scripts/seed_database.py
uvicorn app.main:app --reload                     # :8000
celery -A app.workers.celery_app worker --loglevel=info

# original hackathon app
cd repurposeai && pip install -r requirements.txt
python tests/test_pipeline.py                     # end-to-end smoke test
streamlit run app/dashboard.py
```

The frontend runs standalone with no backend, database or network — that is
deliberate, so it always demos even on venue wifi.

---

## Caveats carried from the code, worth knowing before you trust something

- `backend/README.md` states the service was developed in a sandbox without
  Docker/Postgres/Redis; end-to-end verification was done against SQLite with
  `CELERY_TASK_ALWAYS_EAGER=true`. The Docker stack was **not** executed there.
  Validate it in a Docker-capable environment before relying on it.
- `repurposeai/` ships synthetic CSVs from `scripts/generate_mock_data.py`, with
  three planted reversal signals and two planted reinforcing ones. Its
  `KNOWN_VALIDATION_SETS` real-drug check correctly finds zero matches against
  those placeholder names — intended behaviour, not a bug.
- The frontend has no test suite. Typecheck (`npx tsc -b --noEmit`) plus a
  browser pass is its verification loop.
