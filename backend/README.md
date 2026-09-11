# Repurpose AI — Backend

A production-structured backend for a biotech drug-repurposing intelligence platform. This repository is **backend only** — REST + WebSocket APIs, a PostgreSQL schema, a Celery/Redis job system, and a real (if intentionally simple, swappable) AI/ML pipeline. No UI code lives here; a separate frontend consumes this service over HTTP/WS.

> **Scientific integrity note:** all drug/disease/gene/target/interaction data shipped in `scripts/generate_demo_data.py` is clearly marked `DEMO/SYNTHETIC DATA` in every seeded row's metadata. Drug, gene, and disease *names* are real public terms; the *relationships* between them (which gene associates with which disease, interaction confidence scores, etc.) are synthetic and were generated for this demo only — they are not sourced from any curated biomedical database. Predictions are labeled "computational predictions" throughout and explicitly state they require experimental validation; nothing in this system should be read as a clinical or diagnostic claim.

---

## 1. Tech stack

| Layer | Choice |
|---|---|
| API | FastAPI + Uvicorn (Python 3.12) |
| DB | PostgreSQL + SQLAlchemy 2.x + Alembic |
| Auth | JWT (access + refresh), bcrypt, RBAC |
| Background jobs | Celery + Redis |
| AI/ML | scikit-learn, numpy, scipy, pandas, Biopython |
| Storage | Local disk (dev) or S3-compatible (prod), pluggable |
| Realtime | Native WebSockets + Redis pub/sub relay |
| Tests | pytest, pytest-cov, FastAPI TestClient |
| Packaging | Docker + docker-compose |

## 2. Project layout

```
app/
  core/        config, security (JWT/RBAC), logging, exceptions, constants
  db/          engine/session, declarative base, cross-dialect GUID/JSON types
  models/      SQLAlchemy ORM models (17 tables)
  schemas/     Pydantic request/response models
  api/v1/      one router module per resource
  services/    business logic, called by routers and Celery tasks alike
  ai/          model interfaces, feature engineering, similarity, ranking, explainability
  biotech/     domain queries (genes/targets/evidence/compound similarity) + repurposing orchestrator
  data/        format loaders (CSV/JSON/XLSX/FASTA/FASTQ) and dataset validation
  workers/     Celery app + task modules
  websocket/   connection manager + Redis pub/sub relay + WS routes
  utils/       pagination, file storage adapter, validators, serialization
alembic/       migrations
scripts/       seed_database.py, generate_demo_data.py, create_admin.py
tests/         pytest suite (53 tests, ~82% coverage)
docs/          API_CONTRACT.md for frontend integration
```

## 3. Database schema (overview)

17 tables: `users`, `roles`, `refresh_tokens`, `projects`, `experiments`, `datasets`, `analyses`, `drugs`, `compounds`, `diseases`, `genes`, `targets`, `interactions`, `predictions`, `recommendations`, `notifications`, `audit_logs`, `jobs`. All primary keys are UUIDs; a custom `GUID` type stores them natively on PostgreSQL and as `CHAR(32)` on SQLite (used only by the test suite), so the exact same models run on both without branching. `metadata`-named JSON columns are mapped to a Python attribute called `extra_metadata` to avoid colliding with SQLAlchemy's reserved `Base.metadata`.

Run `alembic upgrade head` to create the schema; see `alembic/versions/` for the generated migration.

## 4. Running locally (no Docker)

Requires PostgreSQL and Redis running locally (or point at any reachable instance).

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # then edit DATABASE_URL / REDIS_URL / JWT_SECRET as needed

alembic upgrade head
python scripts/seed_database.py          # add --reset to wipe and reseed
uvicorn app.main:app --reload            # API on http://localhost:8000

# in separate terminals:
celery -A app.workers.celery_app worker --loglevel=info
celery -A app.workers.celery_app beat --loglevel=info
```

**Note:** this repository was developed and verified inside a sandboxed environment with no Docker/PostgreSQL/Redis daemon available. Full end-to-end verification (server boot, auth, projects/experiments/datasets, the real repurposing pipeline, WebSocket auth) was done against SQLite with `CELERY_TASK_ALWAYS_EAGER=true` (tasks execute synchronously in-process, only for environments without a broker — see `.env`). The application code is Postgres/Redis-native throughout (see `app/db/types.py` for the cross-dialect UUID/JSON handling that makes this possible); running the real `docker compose up --build` stack below was not itself executed in this sandbox, so validate it in a Docker-capable environment before shipping.

## 5. Running with Docker

```bash
cp .env.example .env
docker compose up --build
```

This starts `postgres`, `redis`, `backend` (runs `alembic upgrade head` then Uvicorn), and `worker` (Celery). A `beat` service runs the scheduled cleanup task. `minio` is available under the `s3` profile (`docker compose --profile s3 up`) if you want to exercise the S3 storage backend locally.

- API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

Seed demo data once the stack is up:

```bash
docker compose exec backend python scripts/seed_database.py
```

## 6. Demo credentials

After seeding:

- **Admin:** `admin@repurpose.ai` / `ChangeMe123!` (from `.env` `FIRST_SUPERUSER_*`, change in production)
- **Demo users** (researcher/analyst/viewer roles): see `USER_NAME_ROLES` in `scripts/generate_demo_data.py` for the generated emails (e.g. `elena.vasquez@repurpose.ai`), password `Demo1234!` for all of them.

## 7. AI/ML pipeline

`POST /api/v1/repurposing/run` drives `app/biotech/drug_repurposing.py`, which:

1. Validates the disease exists and has associated gene data.
2. Gathers every drug's known targets and their genes (`app/biotech/target_analysis.py`).
3. Gathers supporting `Interaction` evidence (`app/biotech/evidence_scoring.py`).
4. Computes compound similarity against known-indication reference compounds (`app/biotech/compound_similarity.py`, cosine similarity over physicochemical descriptors).
5. Builds a 7-feature vector per candidate (`app/ai/feature_engineering`).
6. Scores candidates with a `RandomForestClassifier` (`app/ai/models/repurposing.py`) blended with a transparent weighted heuristic.
7. Ranks and normalizes scores (`app/ai/ranking`).
8. Generates a human-readable, evidence-tiered explanation for every candidate (`app/ai/explainability`) — explicitly labeled as a computational prediction, never a clinical claim.
9. Persists `Prediction` rows with the full feature vector, explanation, and model version for reproducibility.

The classifier has no bundled real-world labeled repurposing outcomes (none are publicly redistributable), so it self-calibrates on a synthetic, clearly-labeled bootstrap sample at process start (`DrugRepurposingModel.bootstrap_trained`) — swap that classmethod for a loader over a real labeled dataset to make this production-grade without touching any caller. The `BaseModel` interface (`app/ai/models/base.py`) is designed so RandomForest can be swapped for XGBoost/PyTorch/a GNN later with no change to `app/ai/pipeline.py` or the API layer.

## 8. WebSockets

`/ws/experiments/{id}`, `/ws/analyses/{id}`, `/ws/jobs/{id}`, `/ws/notifications` (auth via `?token=<access_token>` query param). Celery workers run in a separate process from the API, so progress events are published to Redis pub/sub (`ws:<channel>`) by `app/websocket/handlers.py::publish_ws_event` and relayed to connected browser clients by an asyncio task started in `app/main.py`'s lifespan. If Redis is unreachable, publishing/relaying fails silently (logged as a warning) rather than breaking the underlying job — this was exercised directly in this sandbox (no Redis available) and confirmed not to affect API/job correctness.

## 9. Known limitations / honest caveats

- **Not run against real Postgres/Redis/Docker in this environment** — verified against SQLite + Celery eager mode instead (see §4). Run the real stack before considering this "production-verified."
- The repurposing classifier is trained on a synthetic bootstrap sample, not real labeled outcomes (see §7) — by design, and documented in-code.
- Compound similarity uses declared physicochemical properties rather than real cheminformatics fingerprints (no RDKit dependency) — swappable via `app/ai/similarity/similarity_model.py`.
- Rate limiting is configured (`RATE_LIMIT_PER_MINUTE`) but not yet enforced by middleware — add a Redis-backed limiter (e.g. `slowapi`) before internet-facing production use.
- Redis-backed caching (dashboard/reference-data TTLs in config) is configured but not yet wired into the dashboard/reference-data endpoints — the settings exist for the next engineer to plug in.

## 10. Frontend integration

See [`docs/API_CONTRACT.md`](docs/API_CONTRACT.md) for the full endpoint reference. In short: `BASE_API_URL` + JWT bearer auth + REST/JSON + WebSocket for live updates. No HTML is ever returned by the API.
