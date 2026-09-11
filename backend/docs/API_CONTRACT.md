# Repurpose AI — API Contract

This document is the single source of truth for frontend integration. It intentionally repeats information available in Swagger (`/docs`) so a frontend engineer never has to read backend source code.

## Base

- `BASE_API_URL` = `http://localhost:8000/api/v1` (dev) — everything below is relative to this unless noted.
- All responses are JSON. No endpoint ever returns HTML.
- Auth: `Authorization: Bearer <access_token>` header, obtained from `/auth/login`.

## Response envelope

Every REST response — success or failure — follows one shape.

**Success:**
```json
{ "success": true, "data": { /* endpoint-specific payload */ } }
```

**Error:**
```json
{
  "success": false,
  "error": {
    "code": "DATASET_NOT_FOUND",
    "message": "Dataset was not found",
    "details": {}
  }
}
```

Common HTTP status codes: `400` invalid input, `401` not authenticated / invalid token, `403` authenticated but not permitted, `404` not found, `409` conflict (duplicate, invalid state transition), `422` validation error, `429` rate limited, `500` server error (stack traces never leak in `ENVIRONMENT=production`).

## Pagination

Any list endpoint accepts `?page=1&page_size=20` (`page_size` max 200, default 20) and returns:

```json
{
  "success": true,
  "data": { "items": [ /* ... */ ], "page": 1, "page_size": 20, "total": 137, "pages": 7 }
}
```

## Roles & permissions

Roles: `admin`, `researcher`, `analyst`, `viewer`. `admin` has every permission. `researcher`/`analyst` can create and mutate their own projects/experiments/datasets; `viewer` is read-only except for managing their own notifications/recommendations. Ownership is enforced per-project: non-admins only see/modify projects they own (and that project's experiments/datasets/predictions). A `403 AUTHORIZATION_ERROR` means the token is valid but lacks permission; a `401 AUTHENTICATION_ERROR` means the token is missing/invalid/expired.

---

## Authentication (`/auth`)

| Method | Path | Auth | Body | Notes |
|---|---|---|---|---|
| POST | `/auth/register` | none | `{name, email, password, role?}` (`role` defaults to `viewer`; one of `admin/researcher/analyst/viewer`) | 201 on success. `409 EMAIL_TAKEN` if the email exists. |
| POST | `/auth/login` | none | `{email, password}` | Returns `{access_token, refresh_token, token_type, expires_in}`. `401 INVALID_CREDENTIALS`. |
| POST | `/auth/refresh` | none | `{refresh_token}` | Rotates the refresh token (old one is revoked). `401 TOKEN_REVOKED` / `401 TOKEN_EXPIRED`. |
| POST | `/auth/logout` | Bearer | `{refresh_token}` (optional — omit to revoke all of the user's refresh tokens) | |
| GET | `/auth/me` | Bearer | — | Current user profile. |
| PUT | `/auth/me` | Bearer | `{name?, password?}` | Partial update. |

`access_token` expires in `JWT_ACCESS_EXPIRE_MINUTES` (default 30 min); use `/auth/refresh` before/after expiry. `refresh_token` expires in `JWT_REFRESH_EXPIRE_DAYS` (default 7 days) and is single-use (rotated on every refresh).

## Users (`/users`) — admin only

| Method | Path | Body |
|---|---|---|
| GET | `/users?page=&page_size=` | — |
| GET | `/users/{id}` | — |
| PUT | `/users/{id}` | `{name?, role?, is_active?}` |

## Projects (`/projects`)

| Method | Path | Body / Query |
|---|---|---|
| GET | `/projects?page=&page_size=&status=&search=` | `status` ∈ `ACTIVE/ARCHIVED/COMPLETED/ON_HOLD` |
| POST | `/projects` | `{name, description?}` → 201 |
| GET | `/projects/{id}` | — |
| PUT | `/projects/{id}` | `{name?, description?, status?}` |
| DELETE | `/projects/{id}` | — cascades to experiments/datasets/predictions |
| GET | `/projects/{id}/summary` | `{project, experiment_count, dataset_count, analysis_count, prediction_count, completed_experiments, running_experiments, failed_experiments, high_confidence_predictions}` |
| GET | `/projects/{id}/experiments` | paginated |
| GET | `/projects/{id}/datasets` | paginated |
| GET | `/projects/{id}/analyses` | paginated |
| GET | `/projects/{id}/predictions` | paginated |

## Experiments (`/experiments`)

Lifecycle: `DRAFT → QUEUED → RUNNING → ANALYZING → COMPLETED | FAILED | CANCELLED`.

| Method | Path | Body / Query |
|---|---|---|
| GET | `/experiments?page=&page_size=&project_id=&status=&experiment_type=` | `experiment_type` ∈ `drug_repurposing/gene_expression/target_analysis/disease_analysis/compound_similarity/custom` |
| POST | `/experiments` | `{project_id, name, description?, experiment_type, parameters}` → 201, status `DRAFT` |
| GET | `/experiments/{id}` | — |
| PUT | `/experiments/{id}` | `{name?, description?, parameters?, status?}` |
| DELETE | `/experiments/{id}` | — |
| POST | `/experiments/{id}/start` | Queues the experiment for background execution; dispatches a Celery task and returns immediately with status `QUEUED` (or the terminal status, if it already finished by the time the response is built). |
| POST | `/experiments/{id}/cancel` | Only valid from `QUEUED/RUNNING/ANALYZING`; `422 EXPERIMENT_NOT_CANCELLABLE` otherwise. |
| GET | `/experiments/{id}/status` | `{id, status, progress, started_at, completed_at}` — cheap poll endpoint. |
| GET | `/experiments/{id}/results` | `{id, status, analyses: [...], predictions: [...]}` |

For `experiment_type: "drug_repurposing"`, `parameters` **must** include `{"disease_id": "<uuid>", "top_k"?: 20}`. Starting it runs the full repurposing pipeline (see §AI pipeline in README) and persists `Prediction` rows linked to the experiment. Other types run a lighter analysis pass over `parameters.dataset_id` if provided.

Prefer subscribing to `/ws/experiments/{id}` over polling `/status` for live progress.

## Datasets (`/datasets`)

| Method | Path | Body / Query |
|---|---|---|
| GET | `/datasets?page=&page_size=&project_id=&status=&search=` | `status` ∈ `UPLOADED/VALIDATING/VALID/INVALID/PROCESSING/READY/FAILED` |
| POST | `/datasets/upload` | multipart/form-data: `project_id`, `name?`, `description?`, `file` (csv/json/xlsx/xls/fasta/fa/fastq/fq/tsv, max `MAX_UPLOAD_SIZE` bytes — 50MB default) → 201, runs validation synchronously and returns the final status |
| GET | `/datasets/{id}` | — |
| DELETE | `/datasets/{id}` | removes the stored file too |
| GET | `/datasets/{id}/preview?limit=50` | `{id, columns, rows, total_rows_shown}` |
| GET | `/datasets/{id}/metadata` | `{id, row_count, column_count, columns, missing_values, dtypes, basic_statistics, quality_score}` |
| POST | `/datasets/{id}/validate` | Re-runs validation; `{id, is_valid, status, issues, quality_score}` |

Upload errors: `422 UNSUPPORTED_FILE_TYPE`, `422 FILE_TOO_LARGE`, `422 EMPTY_FILE`, `422 PARSE_ERROR` (malformed file for its declared type).

## Biotech reference data

All of these are read-only, paginated, and support `search`/filter query params. No write endpoints are exposed publicly (reference data is managed via `scripts/seed_database.py` or a future admin ingestion pipeline).

| Method | Path | Query params |
|---|---|---|
| GET | `/drugs` | `search`, `drug_class`, `approval_status` |
| GET | `/drugs/{id}` | — |
| GET | `/diseases` | `search`, `category` |
| GET | `/diseases/{id}` | Returns `{disease, associated_gene_count, associated_genes, has_predictions, top_predictions}` |
| GET | `/genes` | `search`, `organism` |
| GET | `/genes/{id}` | — |
| GET | `/targets` | `search`, `target_type`, `gene_id` |
| GET | `/targets/{id}` | — |
| GET | `/compounds` | `search`, `drug_id` |
| GET | `/compounds/{id}` | — |
| GET | `/interactions` | `interaction_type`, `source_type`, `target_type`, `min_confidence` |

`Interaction.source_entity`/`target_entity` are human-readable labels (`"drug:Metformin"`); `source_type`/`source_id`/`target_type`/`target_id` are the machine-queryable references (entity type + UUID).

## Analyses (`/analyses`)

Generic analysis engine, separate from the repurposing-specific pipeline.

| Method | Path | Body |
|---|---|---|
| POST | `/analyses/run` | `{experiment_id, dataset_id?, analysis_type, parameters}` → 202, `{job_id, analysis_id, status}` |
| GET | `/analyses/{id}` | Full `Analysis` row including `results`/`error_message` once finished. |

`analysis_type` ∈ `gene_expression, differential_expression, compound_similarity, target_analysis, disease_analysis, drug_repurposing, dataset_quality, statistical_analysis`. `differential_expression` requires `parameters.group_a_columns`/`group_b_columns` (lists of dataset column names). Most types require `dataset_id`; poll via `GET /analyses/{id}` or subscribe to `/ws/analyses/{id}`.

## Drug repurposing (`/repurposing`)

| Method | Path | Body |
|---|---|---|
| POST | `/repurposing/run` | `{disease_id, project_id?, experiment_id?, parameters: {top_k?: 20}}` → 202, `{job_id, status}` |
| GET | `/repurposing/{job_id}` | Full `Job` row — poll `status` (`QUEUED/RUNNING/COMPLETED/FAILED/CANCELLED`). |
| GET | `/repurposing/{job_id}/results` | `{job_id, status, disease_id, predictions: [...]}` once `COMPLETED`. |

If `project_id` is omitted, predictions are attached to (or a new) "Default Repurposing Workspace" project owned by the caller. `422 INSUFFICIENT_DISEASE_DATA` if the disease has no associated genes in the platform. Prefer `/ws/jobs/{job_id}` over polling.

Each prediction object:
```json
{
  "id": "uuid", "project_id": "uuid", "experiment_id": "uuid|null",
  "drug": { "id": "...", "name": "...", "drug_class": "...", "...": "..." },
  "disease": { "id": "...", "name": "...", "...": "..." },
  "score": 0.71, "confidence": 0.68, "rank": 1,
  "features": { "gene_overlap_count": 3, "gene_overlap_ratio": 0.6, "...": "..." },
  "explanation": {
    "prediction": "X is a computationally predicted repurposing candidate for Y.",
    "confidence": 0.68, "reasons": ["...", "..."],
    "supporting_evidence": [{"type": "computational_prediction", "description": "..."}, {"type": "supporting_evidence", "description": "..."}],
    "disclaimer": "Computational prediction only. Not a clinical or diagnostic claim. Requires experimental and/or clinical validation."
  },
  "model_version": "1.0.0", "created_at": "..."
}
```

## Predictions (`/predictions`)

| Method | Path | Query |
|---|---|---|
| GET | `/predictions?page=&page_size=&project_id=&disease_id=&drug_id=&min_confidence=` | Cross-cutting list/filter view over all persisted predictions (not scoped to one repurposing job). |

## Recommendations (`/recommendations`)

Rule-based, not another ML model — every recommendation cites the exact record that triggered it in `evidence`.

| Method | Path | Body |
|---|---|---|
| GET | `/recommendations?page=&page_size=&status=` | `status` ∈ `ACTIVE/DISMISSED/ACTED_ON` |
| POST | `/recommendations/generate` | `{project_id?}` — scans the caller's project(s) for high-confidence predictions, datasets stuck in `INVALID/FAILED`, and failed experiments; returns the newly created recommendations (already-active duplicates are skipped). |
| PUT | `/recommendations/{id}` | `{status?, priority?}` |
| POST | `/recommendations/{id}/dismiss` | shortcut for `status: DISMISSED` |

## Dashboard (`/dashboard`)

All pre-aggregated — the frontend should never need to compute these client-side.

| Method | Path | Returns |
|---|---|---|
| GET | `/dashboard/overview` | `{total_projects, active_projects, total_experiments, running_experiments, completed_experiments, failed_experiments, total_datasets, analyses_running, predictions_generated, high_confidence_candidates}` |
| GET | `/dashboard/activity?limit=20` | Recent audit-log-derived activity feed. |
| GET | `/dashboard/recent-experiments?limit=10` | |
| GET | `/dashboard/recent-predictions?limit=10` | |
| GET | `/dashboard/system-status` | `{database, redis, celery_workers, environment, version, uptime_seconds}` |
| GET | `/dashboard/metrics` | `{predictions_by_confidence: {low,medium,high}, experiments_by_status, datasets_by_status, analyses_by_type}` |

## Analytics (`/analytics`)

Every endpoint takes `?range=7d|30d|90d|1y|custom` and returns `{range, labels: [...dates], series: {<metric>: [...values]}, summary: {...}}` — one point per day in range, zero-filled for days with no activity.

| Path | Metric |
|---|---|
| `/analytics/experiments` | `experiments_created` |
| `/analytics/projects` | `projects_created` |
| `/analytics/predictions` | `predictions_generated` (+ `summary.average_confidence`) |
| `/analytics/datasets` | `datasets_uploaded` |
| `/analytics/activity` | `actions` (audit log volume) |

## Search (`/search`)

| Method | Path | Query |
|---|---|---|
| GET | `/search?q=<term>` | Returns `{query, results: {drugs, diseases, genes, compounds, projects, experiments, datasets}, total_results}`, each grouped list capped at 8 items. |

## Notifications (`/notifications`)

| Method | Path | Body |
|---|---|---|
| GET | `/notifications?page=&page_size=` | All of the caller's notifications, newest first. |
| GET | `/notifications/unread?page=&page_size=` | Same shape plus a top-level `unread_count`. |
| PUT | `/notifications/{id}/read` | — |
| PUT | `/notifications/read-all` | `{marked_read: <count>}` |

Notification types: `experiment_started, experiment_completed, experiment_failed, analysis_completed, analysis_failed, prediction_generated, dataset_validation_failed, high_confidence_candidate, system`. Also delivered live via `/ws/notifications`.

## Audit logs (`/audit-logs`) — admin only

| Method | Path | Query |
|---|---|---|
| GET | `/audit-logs?page=&page_size=&action=&resource_type=&user_id=` | Every mutating action in the system (login, project/experiment/dataset CRUD, analysis/prediction generation, permission changes, etc.) |

## Health (`/health` and `/api/v1/health`)

| Method | Path | Auth |
|---|---|---|
| GET | `/health` (root) or `/api/v1/health` | none |
| GET | `/api/v1/health/database` | none |
| GET | `/api/v1/health/redis` | none |

---

## WebSockets

Base: `ws://localhost:8000` (dev). Auth is a query parameter (browsers can't set headers on the WS handshake): `?token=<access_token>`. An invalid/missing token closes the socket with code `4401`.

| Path | Scope |
|---|---|
| `/ws/experiments/{experiment_id}` | Progress for one experiment's background run. |
| `/ws/analyses/{analysis_id}` | Progress for one analysis job. |
| `/ws/jobs/{job_id}` | Progress for one generic background job (repurposing runs, dataset processing). |
| `/ws/notifications` | The authenticated user's own live notification stream (no id in the path — scoped by token). |

Every event is a JSON text frame:

```json
{
  "event": "progress",
  "job_id": "...",
  "status": "RUNNING",
  "progress": 65,
  "message": "Scoring and ranking candidates",
  "timestamp": "2026-01-01T00:00:00+00:00"
}
```

`event` ∈ `started | progress | completed | failed | notification | queued`. For `/ws/notifications`, `event` is always `notification` and the payload additionally carries `notification_id`, `title`, `message`, `notification_type`. Clients should treat unknown extra fields as forward-compatible and ignore them.

**Recommended flow:** call the REST endpoint that kicks off work (`/experiments/{id}/start`, `/analyses/run`, `/repurposing/run`) to get an id, open the matching WebSocket to drive a live progress UI, and fall back to polling the equivalent REST GET endpoint if the socket disconnects.

---

## Errors reference (non-exhaustive, self-describing via `error.code`)

`NOT_FOUND`, `VALIDATION_ERROR`, `AUTHENTICATION_ERROR`, `AUTHORIZATION_ERROR`, `CONFLICT`, `FILE_PROCESSING_ERROR`, `RATE_LIMIT_EXCEEDED`, `DATABASE_ERROR`, `INTERNAL_SERVER_ERROR`, plus resource-specific codes like `PROJECT_NOT_FOUND`, `DATASET_NOT_FOUND`, `EXPERIMENT_NOT_CANCELLABLE`, `EMAIL_TAKEN`, `INVALID_CREDENTIALS`, `TOKEN_REVOKED`, `TOKEN_EXPIRED`, `UNSUPPORTED_FILE_TYPE`, `FILE_TOO_LARGE`, `INSUFFICIENT_DISEASE_DATA`. Always branch UI behavior on `error.code`, not `error.message` (message text may change; code is stable).
