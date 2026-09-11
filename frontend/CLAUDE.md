# CLAUDE.md

Frontend for **RepurposeAI** — computational drug repurposing for rheumatoid
arthritis. Standalone React/Vite app, no backend yet.

Upstream pipeline: https://github.com/sahas03/RepurposeAI (Python + Streamlit).
This repo replaces its Streamlit UI. The Python side is unchanged and is *not*
vendored here — only the two CSVs in `public/data/`.

## Commands

```bash
npm run dev          # vite, port 5173 (.claude/launch.json uses 5199)
npm run build        # tsc -b && vite build
npx tsc -b --noEmit  # typecheck only — run this before claiming a change works
```

There are no tests. Typecheck plus a browser pass is the verification loop.

---

## The rule that matters most: nothing on screen is authored

Every number in the UI is computed live, in-page, from `public/data/*.csv` by the
TypeScript port in `src/engine/`. **Do not hardcode a score, a count, a
percentage, or an example drug name into a component.** If a value is needed and
the engine does not produce it, derive it from `dataset`/`result` in a `useMemo`,
or add it to `PipelineResult`.

This is the project's whole credibility argument. A judge who spots one invented
number discounts all of them.

### Provenance is mandatory, not decorative

Any surface showing numbers must declare where they came from, via
`<Provenance kind={...} />` (`src/components/ui/Hud.tsx`). Kinds:
`synthetic | real | uploaded | computed | proxy | standby`.

### Honest labelling rules

- The shipped dataset is **synthetic**. Gene symbols (`GENE0000`) and compound
  ids (`drug_042`) are placeholders, not biology. Never write copy that implies
  otherwise.
- Two validation checks exist and must **never** be merged or presented
  interchangeably:
  - `checkRecovery()` — real known-drug recovery. Needs real compound names.
    Correctly returns zero matches on the current data. That is the intended
    behaviour, not a bug to paper over.
  - `syntheticGroundTruth()` — the planted-signal check. Tests ranking math only.
- Inactive subsystems are shown as inactive, never as green ticks. The Lipinski
  screen genuinely cannot run (no structure descriptors) and reports STANDBY with
  its neutral `0.5`, mirroring the Python when `smiles_lookup.csv` is absent.
- The word "clinical" appears only to say this is not that.
- `src/components/sections/Footer.tsx` holds the **honesty ledger** — the
  canonical real/stand-in table. If you change what is real, update it there.

---

## Architecture

```
src/engine/     TS port of the Python. Keep literal — these are diffed by eye.
  loader.ts       <- data_loader.py        CSV parse, harmonize_genes
  scoring.ts      <- signature_matching.py cosine, WTCS, top_contributing_genes
  filters.ts      <- filters.py            Lipinski, novelty, combine_scores
  validate.ts     <- validate.py + app/validation_helpers.py
  run.ts          stage orchestration, measured timings, STAGES metadata
src/api/client.ts THE ONLY BACKEND SEAM. Nothing above it imports engine/ directly.
src/store/        zustand state, theme, and the non-React pointer bus
src/three/        WebGL environment (one canvas behind the whole app)
src/components/   chrome | ui | pipeline | viz | candidates | sections
```

`STAGES` in `run.ts` is the single source of truth for the six pipeline stages
(id, index, title, copy, method detail). Nav, spine, drawers and the discovery
sequence all read from it. Add a stage there, not in a component.

### Backend integration

Implement `RepurposeClient` over `fetch` and swap the final export of
`src/api/client.ts`. `src/engine/types.ts` mirrors the Python DataFrame columns,
so the response shapes should need no translation. `onStage` drives the discovery
sequence and maps cleanly onto SSE; a single blocking call also works.

---

## Design language

One idea, applied everywhere: **the product is about two opposing signals.**

- `ember` = disease direction (up-regulated, pathological, reinforcing)
- `mint` = corrective direction (reversal, the thing we are looking for)
- `signal` (blue) = down-in-disease
- `iris` = the model/AI layer and known references. Use sparingly.
- `amber` = proxy screens and caveats

Colour carries meaning. Do not pick a colour because it looks good in a slot —
pick the one whose meaning fits. Notably: **mint never appears in the disease
signature view**, because nothing has corrected anything yet.

Tokens live in `src/index.css` as `--c-*` triples, consumed by Tailwind semantic
names (`text-ink`, `border-line`, `bg-mint`). The 3D layer has its own mirrored
table in `src/three/palette.ts` — it must never read CSS vars at runtime (style
recalc every frame). **Change a colour in both places.**

Panels come in weights (`GlassPanel kind=`): `primary | secondary | metric |
data | warning | evidence`. Uniform cards are the fastest way to make this look
like a template — pick the weight that matches the content's importance.

Both themes are first-class. Light is a clinical bench, **not** `background:
white`. Any new surface must be checked in both.

---

## Performance invariants

The reactive background costs the React tree **zero renders**. Preserve that.

- Pointer position, scroll, pipeline "energy" and theme blend live in
  `src/store/pointer.ts` — a plain mutable module object written by passive DOM
  listeners and read inside `useFrame`. Never route per-frame values through
  React state.
- **Never allocate inside `useFrame`.** No `new THREE.Vector3()`, no `.clone()`,
  no array literals. Pre-allocate in `useMemo` and `.copy()` into it. (Bit me
  once in `MoleculeField` — see the `world[]` mirror array.)
- Geometry counts scale off `detectTier()`. Add new 3D work to all three tiers.
- Particle systems reuse typed arrays and set `needsUpdate` on the attribute.
- The loop halts on `!pointer.visible` (tab hidden).
- `prefers-reduced-motion` keeps the composition, drops the motion — check
  `pointer.reducedMotion` or framer's `useReducedMotion()`.

---

## Gotchas that have already bitten

1. **`erasableSyntaxOnly: true`** in `tsconfig.app.json` forbids TS constructor
   parameter properties (`constructor(private x: number)`). Declare fields
   explicitly. Also `verbatimModuleSyntax` — use `import type` for type-only
   imports or the build fails.
2. **CSS grid: use `minmax(0,1fr)`, never bare `1fr`**, when a column contains a
   wide child (heatmap grid, SVG, table). A bare `1fr` has `min-width: auto` and
   the column blows past its container.
3. **`selected` vs `detail` in `useApp`.** `selected` is the candidate
   highlighted across visualisations and is set *automatically* after a run.
   `detail` is what opens the drawer. Wiring the drawer to `selected` makes it
   pop open unbidden on every run. Use `openDetail()` for click handlers.
4. **Additive blending washes out in light mode.** Every additive material's
   intensity is multiplied by a `(x + dark * y)` factor so it recedes when
   `pointer.dark` → 0. New additive layers need the same treatment.
5. **`EmptyField` is exported from `SignatureSection.tsx`** and reused by every
   section. Slightly odd home; it is the shared empty state, not signature-specific.
6. React is pinned to **18.3.1** for `@react-three/fiber` v8 / `drei` v9
   compatibility. Tailwind is **v3**, not v4. Don't casually bump these.

---

## Scope note

This repo is the frontend only. Integration with the Python backend is a later,
separate task — the seam is ready, but do not vendor backend code in here or
reach for the upstream repo's Python files when making frontend changes.
