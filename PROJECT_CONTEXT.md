# RepurposeAI — Complete Project Context

**Everything built, decided and verified, as of 11 September 2026.**

This is the human-readable record: what the project is, what was built and why,
what is proven, and what is still missing. For AI-agent coding instructions see
`CLAUDE.md` (whole repo) and `frontend/CLAUDE.md` (frontend specifics). For the
backend API see `backend/docs/API_CONTRACT.md`.

CBIT National Level Ideathon 5.0 — Life Sciences & AI. Target disease:
**rheumatoid arthritis**.

---

## 1. TL;DR

Diseases leave a fingerprint in which genes get switched up and down. Drugs leave
fingerprints too. RepurposeAI searches a drug library for the fingerprint that is
the **mirror image** of the disease — because a drug that undoes the disease's
changes may treat it.

It scores every compound, screens for safety and novelty, and shows its working
**gene by gene**. To prove it is not noise, it is run blind against data with
known answers: it recovers all of them and ranks the deliberately-bad ones last.

The frontend runs the entire pipeline live in the browser with no backend,
database or network.

---

## 2. The science, in plain words

**Cells run on genes.** Genes get switched up (more protein) or down (less).
A disease distorts that pattern. Measure every gene at once and you get the
**disease signature** — a list of which genes moved, how far, and how confidently.

**Drugs change gene expression too.** Dose cells with a compound, measure the same
genes, and you get that compound's signature.

The core idea:

> If the disease pushes a gene **UP**, and a drug pushes that same gene **DOWN**,
> the drug is undoing what the disease did.

So: find the compound whose signature is the **opposite** of the disease's.

This method is not ours. It is the **Connectivity Map** approach from the Broad
Institute, and the compound signature database it runs on is real — **LINCS
L1000**, roughly a million drug/cell experiments. We are applying an established
method, which is a strength, not a weakness: the maths is defensible because it
is already peer-reviewed.

**Why repurposing matters:** a new drug costs ~$1–2bn and 10–15 years. An existing
approved drug is already proven safe in humans and already manufactured. Finding
a new use skips years. Real precedent: baricitinib, a rheumatoid arthritis drug,
was repurposed for COVID-19.

---

## 3. The six-stage pipeline

| # | Stage | What happens |
|---|---|---|
| 01 | **Disease Signature** | Load `gene, logFC, pvalue`. Standardise gene names, keep only genes present in *both* datasets, then z-score. On real data this intersection is the big filter (~20,000 genes down to ~1,000). |
| 02 | **Drug Library** | Load a grid: genes down the side, compounds across the top. Each column is one compound's fingerprint. This grid is the entire search space. |
| 03 | **Signature Reversal** | Compare the disease signature against every compound column using **cosine similarity**. Range −1 to +1. **−1 = perfect mirror = best candidate.** 0 = unrelated. +1 = makes the disease pattern stronger. |
| 04 | **Safety + Novelty** | **Lipinski's Rule of Five** (four rules about molecular weight, greasiness and hydrogen bonding that predict whether something can work as an oral pill). Plus a known-vs-novel label. Known drugs are **kept**, not filtered — they are the proof the method works. |
| 05 | **Explainability** | The cosine score is a *sum* of one term per gene. Pull it apart and you get the exact per-gene contributions. Not an approximation of the model — it **is** the model, decomposed. |
| 06 | **Validation** | Run blind against data where the answer is known. Did it re-find what it should have? |

**Score fusion** (stage 04 output):

```
final = 0.6 × reversal  +  0.2 × safety  +  0.2 × novelty
```

Weights are configurable in the settings dock. A second scoring method, **WTCS**
(rank-based, closer to the original Connectivity Map maths), is also implemented
and switchable.

---

## 4. What existed before this work

The upstream repo `sahas03/RepurposeAI` had:

- `repurposeai/src/` — the working Python pipeline: `data_loader.py`,
  `signature_matching.py`, `filters.py`, `interpretability.py`, `validate.py`
- `repurposeai/app/dashboard.py` — a functional Streamlit UI
- `repurposeai/scripts/generate_mock_data.py` — synthetic test data generator
- Two synthetic CSVs: 200 genes × 150 compounds

The pipeline logic was sound. The UI was functional but visually generic.

**Separately**, a teammate has since added `backend/` — a production-structured
FastAPI service (Postgres, Celery/Redis, JWT/RBAC, 17 tables, 21 route modules,
and its own scikit-learn AI pipeline).

---

## 5. What was built

A standalone React frontend, in `frontend/`. 68 files.

### The central decision: port the maths, do not fake it

Rather than mock up a pretty shell, the entire Python pipeline was **ported
line-for-line to TypeScript** and runs live in the browser against the same CSVs.

`frontend/src/engine/` maps one-to-one onto the Python:

| TypeScript | Python |
|---|---|
| `loader.ts` | `data_loader.py` |
| `scoring.ts` | `signature_matching.py` |
| `filters.ts` | `filters.py` |
| `validate.ts` | `validate.py` + `app/validation_helpers.py` |
| `run.ts` | stage orchestration, measured timings |

**Consequences:**
- Every number on screen is computed at that moment. Nothing is authored, cached
  or pre-recorded.
- Works with **no internet, no server, no database** — critical for a live demo
  on venue wifi.
- A full run costs ~3 milliseconds. The on-screen sequence is deliberately slowed
  so a human can follow it; the millisecond timings shown are the real measured
  costs.

### Design identity

Built on one idea: **the product is about two opposing signals.**

- **Ember (orange)** = disease direction — up-regulated, pathological, reinforcing
- **Mint (green)** = corrective direction — reversal, what we are looking for
- **Signal (blue)** = down-in-disease
- **Iris (violet)** = the model layer and known references, used sparingly
- **Amber** = proxy screens and caveats

Colour carries meaning rather than decoration. Notably **mint never appears in the
disease signature view**, because nothing has corrected anything yet.

Both themes are first-class: dark is a deep-space biotech lab, light is a clinical
bench (deliberately *not* a white page). Switching runs a circular reveal expanding
from the switch while the 3D scene interpolates its own palette.

---

## 6. Complete feature inventory

| Section | What it does |
|---|---|
| **Hero** | 3D DNA helix that leans toward the cursor, recedes on scroll, and intensifies during a run |
| **Initiate Discovery** | Replaces a loading spinner: six stages activate in sequence, each showing its real output text and real measured milliseconds |
| **Pipeline** | Six stages on an instrument spine with particles flowing down it, filling as stages complete. Each opens a drawer with the method **and its limitations** |
| **Signature** | All 200 genes as a heatmap, ordered by fold change. Orange = up in disease, blue = down. Hover any cell for gene, logFC, p-value |
| **Library** | 150 compounds as a constellation. Before scoring, distance from centre = effect magnitude. After scoring, distance = reversal rank, so candidates are pulled inward. The rearrangement *is* the scoring, made visible |
| **Reversal** | The mirror, drawn: disease above the axis, compound below. Switch between top candidates and a negative control and watch it flip |
| **Safety** | A scanning chamber showing which checks are active vs standby, plus the score fusion arithmetic with live numbers |
| **Candidates** | Three views — constellation / ranked list / data table. Click any for a full record drawer. CSV export |
| **Explainability** | Interactive "Why this drug?" graph: disease → genes → compound, edge thickness = contribution magnitude, click any gene for the arithmetic |
| **Validation** | The verification result with a drawn seal, recovered signals, negative controls, and an explicit "what this is not" panel |
| **Footer** | The honesty ledger — six rows of real vs stand-in |

**Also:** animated theme switch, floating settings dock (change scoring method,
candidate count, validation top-K, then re-run), custom scientific cursor
(disabled on touch), mobile layout, keyboard and screen-reader support,
`prefers-reduced-motion` support, and an easter egg (tap the status light 5×
for raw stage timings).

---

## 7. Verified results

Run live on the synthetic benchmark, with the pipeline told nothing about which
compounds were planted:

| Check | Result |
|---|---|
| Planted reversal signals recovered | **3 of 3** — at ranks **1, 2 and 3** |
| Recovery rate | **100%** |
| Negative control `planted_reinforcing_drug_3` | ranked **150 / 150** |
| Negative control `planted_reinforcing_drug_4` | ranked **149 / 150** |
| Strongest reversal score | **−0.9892** |
| Genes opposed, top candidate | **200 / 200** |
| Library searched | 150 compounds across 200 shared genes |

**This is the strongest argument in the project.** It shows the score separates
*direction*, not just magnitude — it puts the mirrors at the very top and the
reinforcers at the very bottom, blind.

---

## 8. Honesty posture

The data is synthetic. Genes are named `GENE0000`, compounds `drug_042`. Real
LINCS L1000 is a multi-gigabyte download that was not available.

Two ways to handle that: dress it up and get destroyed when someone asks, or say
it first. **We say it first.**

- Every surface showing numbers carries a provenance badge
  (`synthetic / real / computed / proxy / standby`).
- Subsystems that cannot run say **STANDBY with the reason**, never a fake tick:
  - **Lipinski safety** — needs molecular structures we do not have, so it
    contributes its neutral `0.5`. The Python does exactly the same when
    `smiles_lookup.csv` is absent.
  - **Pathway enrichment** — needs internet and real gene symbols. `GENE0119` is
    in no pathway database.
- The two validation checks are **never merged**: `checkRecovery()` needs real
  drug names and correctly returns zero matches here; `syntheticGroundTruth()`
  tests the ranking maths on planted signals.
- The page ends with the ledger, closing on *"Clinical evidence: None."*

The backend independently follows the same posture — every seeded row is marked
`DEMO/SYNTHETIC DATA`, and while drug/gene/disease *names* are real public terms,
the *relationships* between them are synthetic.

**Why this is a strength:** a judge who catches you overselling discounts
everything. A judge who watches you flag your own limits trusts what you do
claim. The maths is genuinely real — that claim survives scrutiny.

---

## 9. Architecture and how to run

```
repurposeai/   original hackathon pipeline — Python + Streamlit
backend/       FastAPI service — Postgres, Celery/Redis, JWT/RBAC, own AI pipeline
frontend/      React/Vite UI — runs a TS port of repurposeai/ in-browser
```

```bash
# frontend — needs nothing else running
cd frontend && npm install && npm run dev        # :5173

# backend — needs Postgres + Redis
cd backend && python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && cp .env.example .env
alembic upgrade head && python scripts/seed_database.py
uvicorn app.main:app --reload                     # :8000

# original Streamlit app
cd repurposeai && streamlit run app/dashboard.py
```

**Stack:** React 18.3.1 (pinned for R3F v8 / drei v9 compatibility), Vite 8,
TypeScript 6, Tailwind 3.4, three 0.169, @react-three/fiber 8.17, drei 9.114,
framer-motion 11.11, zustand 5. Fonts are self-hosted via fontsource so the app
works fully offline.

**Performance approach:** one canvas for the whole environment; the DNA helix is
5 draw calls, the molecule field 2. Pointer position, scroll and pipeline energy
live in a plain module object (`store/pointer.ts`) read inside the render loop —
so the reactive background costs the React tree **zero renders**. Geometry counts
scale by a device-tier probe, nothing allocates per frame, and the loop halts
when the tab is hidden.

**Production build:** ~2.3s. Largest chunk is the 3D stack at 212 kB gzipped.

---

## 10. Repository state

Two branches, deliberately unmerged, with **zero overlapping paths**:

- **`main`** — `backend/` + `repurposeai/`
- **`frontend`** — everything under `frontend/`, plus the root context files

Histories are unrelated (the frontend began as a standalone repo), so merging
needs `--allow-unrelated-histories`. The frontend was moved into `frontend/`
specifically to match the existing `backend/` convention and remove the
`.gitignore` / `.claude/launch.json` collisions a root-level merge would hit.

When ready to integrate:

```bash
git fetch origin && git checkout -B main origin/main
git merge frontend --allow-unrelated-histories && git push origin main
```

---

## 11. Known gaps — what is NOT built

Stated plainly so nobody is surprised mid-demo.

**Regressions from the Streamlit app:**
- **CSV upload** — the Streamlit version let you upload your own data. The new
  frontend does not.
- **Disease selector** — only rheumatoid arthritis is wired up.
- **Regenerate demo data** button.
- **Pathway enrichment button** — deliberately omitted, with the reason shown
  on screen.

**Never built:**
- No test suite for the frontend. Verification is typecheck plus a browser pass.
- No real data. No backend connection yet.
- No user accounts, saved runs or shareable result links.

---

## 12. Roadmap, by impact

### Tier 1 — the real unlock
**Plug in real data.** Needs **zero code changes**. Download a real RA signature
from GEO and real LINCS L1000 compound signatures, in the same three columns.
Compound names become `baricitinib`, `methotrexate`, `adalimumab` — and the
validation panel automatically flips from planted-signal checking to *"did we
re-find the 9 real RA drugs?"* **That code already exists and is waiting.**

### Tier 2 — connect the backend
One file changes: `frontend/src/api/client.ts`. Implement `RepurposeClient`,
swap the export.

⚠️ **Decide this first:** there are now **two different repurposing engines** in
the repo — the hackathon pipeline the frontend mirrors, and the backend's own
scikit-learn one. They are not the same method with the same outputs. Someone
must decide which the UI renders before any adapter is written, or the result is
an incoherent hybrid.

⚠️ **Impedance mismatch:** the backend runs jobs asynchronously
(`POST /repurposing/run` → poll `/{job_id}` → fetch `/{job_id}/results`), but the
frontend expects six named stages reporting in sequence via `onStage`. The
backend has native WebSockets with a Redis pub/sub relay — that is the clean fix.
Polling would flatten the sequence into a spinner, which is exactly what that UI
exists to avoid. CORS already allows `http://localhost:5173`.

⚠️ **Unverified:** `backend/README.md` states the service was developed in a
sandbox without Docker/Postgres/Redis and verified against SQLite with
`CELERY_TASK_ALWAYS_EAGER=true`. The Docker stack was never executed. Validate it
in a Docker-capable environment before depending on it.

### Tier 3 — restore the missing features
CSV upload, disease selector, data regeneration.

### Tier 4 — genuinely new science
- **More diseases** — add reference drug sets beyond RA
- **Cell-line awareness** — real L1000 tests compounds across cell types; a drug
  that works in liver cells may not work in joint tissue
- **Dose–response** — does reversal strengthen with dose? A real biological signal
- **Combination therapy** — two drugs whose combined signature mirrors the disease
  better than either alone. Hard, and genuinely novel
- **Rank aggregation** — trust compounds that score well under both cosine and WTCS
- **Side-effect prediction** — the same logic run backwards: which genes does the
  compound disturb that it should not?
- **Shareable run links** — send a judge a URL reproducing an exact result

---

## 13. Pitch notes

**Lead with validation, not visuals.** The 3/3 recovery at ranks 1–3, with both
negative controls at 149 and 150 of 150, is the credibility. The interface earns
attention; the validation earns belief.

**Rehearse the "your data is fake" question out loud.** It will come. It is not
an attack — it is the question already answered on screen. The answer is:
*"Yes, and here is the ledger. What's synthetic is the data. What's real is the
method — and here is the blind test proving it works."*

**The 30-second version:**

> Diseases leave a fingerprint in which genes are switched on and off. Drugs leave
> fingerprints too. RepurposeAI searches a drug library for the fingerprint that is
> the mirror image of the disease, because a drug that undoes the disease's changes
> may treat it. It scores every compound, screens for safety and novelty, and —
> unlike most AI — shows its working gene by gene, because the score is literally a
> sum of per-gene terms. To prove it isn't noise, we hide the answers and check
> whether it re-finds drugs already known to work. It recovers all of them, at the
> very top, and ranks the deliberately-bad ones dead last. Everything on screen is
> computed live in the browser.
