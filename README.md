# RepurposeAI — Frontend

A cinematic interface for computational drug repurposing in **rheumatoid arthritis**.

This is a standalone frontend for the [`sahas03/RepurposeAI`](https://github.com/sahas03/RepurposeAI)
pipeline. It runs today with no backend: the Python scoring logic has been ported
to TypeScript and executes in the browser against the repository's own CSVs, so
every number on screen is genuinely computed rather than authored.

```bash
npm install
npm run dev      # http://localhost:5173
npm run build
```

---

## What is real, and what is a stand-in

The interface is deliberate about this, and the page itself ends with the same
ledger. Nothing here should be read as a scientific claim.

| Layer | Status | Detail |
|---|---|---|
| Scoring math | **Real** | Cosine reversal, WTCS, score fusion, gene-level decomposition and the recovery check are ported line-for-line from `src/*.py`. |
| Disease signature | Synthetic | From `scripts/generate_mock_data.py`. Gene symbols are placeholders. |
| Compound library | Synthetic | 150 placeholder identifiers, 3 with a planted reversal signal, 2 reinforcing. |
| Lipinski safety screen | Standby | Implemented, but needs a structure descriptor table. Contributes its neutral `0.5`, exactly as the Python does when `smiles_lookup.csv` is absent. |
| Pathway enrichment | Standby | Needs the Enrichr API and real HGNC symbols. |
| Clinical evidence | **None** | Nothing in this build is a clinical, experimental or literature claim. |

---

## Backend integration

Every component talks to the pipeline through one interface. Nothing above that
layer knows whether the work happens in-page or on a server.

```
src/api/client.ts        <- the only seam. Swap localClient for an HTTP client.
src/engine/types.ts      <- response shapes, mirroring the Python DataFrame columns
```

To wire up the Python service, implement `RepurposeClient` over `fetch` and
change the final export in `src/api/client.ts`:

```ts
export const client: RepurposeClient = httpClient(import.meta.env.VITE_API_URL)
```

The three methods a backend must provide:

| Method | Returns |
|---|---|
| `listDatasets()` | dataset descriptors, including a `disclosure` string shown verbatim in the UI |
| `loadDataset(id)` | harmonised `Dataset` — disease rows, gene list, drug list, genes x drugs matrix |
| `run(dataset, settings, onStage)` | a `PipelineResult`, reporting each stage through `onStage` as it completes |

`onStage` is what drives the discovery sequence. A streaming endpoint (SSE or
websocket) maps onto it directly; a single blocking call also works, the stages
just resolve together.

---

## Architecture

```
src/
├── engine/          TypeScript port of the Python pipeline
│   ├── loader.ts      data_loader.py        - CSV parsing, gene harmonisation
│   ├── scoring.ts     signature_matching.py - cosine, WTCS, gene contributions
│   ├── filters.ts     filters.py            - Lipinski, novelty, score fusion
│   ├── validate.ts    validate.py           - known-drug + planted-signal recovery
│   └── run.ts         stage orchestration and measured timings
├── api/client.ts    the backend seam
├── store/           zustand app state, theme, and a non-React pointer bus
├── three/           the WebGL environment
│   ├── BioUniverse    canvas root, theme interpolation, scroll-driven recession
│   ├── DNAHelix       pointer-reactive double helix with travelling particles
│   ├── MoleculeField  procedural molecules, 2 draw calls for the whole field
│   ├── GeneNetwork    node graph with pulses along its edges
│   └── Ambient        particle shells, volumetric haze, instrument grid
└── components/
    ├── chrome/      nav, theme switch, system status, cursor, control dock
    ├── ui/          panels, buttons, HUD primitives, drawer, reveals
    ├── pipeline/    the six-stage spine and its method drawers
    ├── viz/         drug constellation
    ├── candidates/  constellation / ranked / table views, detail drawer
    └── sections/    one file per page band
```

### Design language

The identity is built on one idea: this product is about **two opposing
signals**. Ember is the disease direction, mint is the corrective direction, and
every visualisation speaks that language — the helix base pairs, the signature
field, the reversal mirror, the constellation. Colour carries meaning rather
than decoration.

Both themes are first-class. Dark is a deep-space biotech lab; light is a
clinical bench, not a white page. Switching runs a circular View Transition
expanding from the switch itself while the WebGL scene interpolates its own
palette, so the environment changes state rather than repainting.

### Performance

- One `<canvas>` for the whole environment; the DNA helix is 5 draw calls, the
  molecule field 2.
- Pointer, scroll and pipeline "energy" live in a plain module object
  (`store/pointer.ts`) read inside `useFrame` — the reactive background costs
  the React tree zero renders.
- Geometry counts scale by a device tier probe; particle systems reuse
  pre-allocated typed arrays and allocate nothing per frame.
- The render loop halts when the tab is hidden, and the scene fades back as the
  reader scrolls into content.
- `prefers-reduced-motion` keeps the composition and drops the motion.

### Accessibility notes

The custom cursor is disabled on coarse pointers. Interactive nodes carry focus
rings and accessible labels, charts use `role="img"` with descriptive labels,
and the drawer handles Escape and restores scroll.

---

## Data

`public/data/` holds the two CSVs copied from the upstream repository:
`disease_signature.csv` (gene, logFC, pvalue) and `l1000_matrix.csv`
(genes x drugs, z-scored). Regenerate them upstream with
`python scripts/generate_mock_data.py`, or drop in real exports with the same
columns — the loader needs no change.
