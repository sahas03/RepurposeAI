/**
 * client.ts
 * The single seam between the UI and the pipeline.
 *
 * Two implementations of `RepurposeClient` live behind this seam:
 *
 *   httpClient  (./http.ts)  calls the FastAPI service in backend/, which runs
 *                            the real Python pipeline in repurposeai/src/.
 *                            This is the default and the only live path.
 *   localClient (below)      runs the TypeScript port in src/engine/ in-page.
 *                            Kept as an offline fallback; see the export note.
 *
 * The export at the bottom picks between them from `VITE_API_URL`.
 *
 * Ordering note: `loadDataset()` stays client-side in BOTH implementations.
 * The UI reads `dataset.matrix` directly (reversal mirror, explain graph), and
 * the backend does not ship the matrix over the wire.
 */
import type { SafetyTable } from '@/engine/filters'
import { harmonize, parseDiseaseSignature, parseL1000Matrix } from '@/engine/loader'
import { runPipeline, type StageReport } from '@/engine/run'
import { httpClient } from './http'
import { topContributingGenes, zscoreDiseaseSignature } from '@/engine/scoring'
import type {
  Dataset,
  GeneContribution,
  PipelineResult,
  PipelineSettings,
} from '@/engine/types'

export interface DatasetDescriptor {
  id: string
  label: string
  provenance: Dataset['provenance']
  /** Shown verbatim in the UI. Must describe what the data actually is. */
  disclosure: string
  diseasePath: string
  matrixPath: string
}

export const DATASETS: DatasetDescriptor[] = [
  {
    id: 'synthetic-benchmark',
    label: 'Synthetic Benchmark',
    provenance: 'synthetic',
    disclosure:
      'Computer-generated benchmark from scripts/generate_mock_data.py. Gene symbols (GENE0000) and compound identifiers (drug_042) are placeholders, not real biology. Three compounds carry a deliberately planted reversal signal and two carry a reinforcing one, so the ranking can be checked against known ground truth. Every score shown is computed live from these files.',
    diseasePath: 'data/disease_signature.csv',
    matrixPath: 'data/l1000_matrix.csv',
  },
]

export interface RepurposeClient {
  listDatasets(): DatasetDescriptor[]
  loadDataset(id: string): Promise<Dataset>
  run(
    dataset: Dataset,
    settings: PipelineSettings,
    onStage: (r: StageReport) => void,
  ): Promise<PipelineResult>
  /**
   * Per-gene decomposition of one candidate's score. Async because the HTTP
   * implementation asks the Python for it; the local one answers immediately.
   */
  explain(datasetId: string, drug: string, topN: number): Promise<GeneContribution[]>
}

const cache = new Map<string, Dataset>()

/** Runs the ported pipeline in-page. Zero network, works offline at a venue. */
export const localClient: RepurposeClient = {
  listDatasets: () => DATASETS,

  async loadDataset(id) {
    const hit = cache.get(id)
    if (hit) return hit

    const d = DATASETS.find((x) => x.id === id)
    if (!d) throw new Error(`Unknown dataset "${id}".`)

    const base = import.meta.env.BASE_URL
    const [diseaseText, matrixText] = await Promise.all([
      fetch(base + d.diseasePath).then(assertOk(d.diseasePath)),
      fetch(base + d.matrixPath).then(assertOk(d.matrixPath)),
    ])

    const ds = harmonize(parseDiseaseSignature(diseaseText), parseL1000Matrix(matrixText), {
      id: d.id,
      label: d.label,
      provenance: d.provenance,
    })
    cache.set(id, ds)
    return ds
  },

  async explain(datasetId, drug, topN) {
    const ds = await this.loadDataset(datasetId)
    const diseaseVec = zscoreDiseaseSignature(ds.disease.map((d) => d.logFC))
    return topContributingGenes(ds, diseaseVec, drug, topN)
  },

  run(dataset, settings, onStage) {
    // No structure descriptor table ships with the repo, so the Lipinski
    // screen stays on standby and combine_scores() uses its neutral 0.5 -
    // exactly the behaviour of the Python when smiles_lookup.csv is absent.
    const safetyTable: SafetyTable | null = null
    return runPipeline(dataset, settings, safetyTable, onStage)
  },
}

function assertOk(path: string) {
  return async (res: Response) => {
    if (!res.ok) throw new Error(`Could not read ${path} (HTTP ${res.status}).`)
    return res.text()
  }
}

/**
 * Backend integration point — now wired up.
 *
 * `VITE_API_URL` selects the engine:
 *
 *   set    -> httpClient, and every score comes from repurposeai/src/*.py
 *   unset  -> localClient, the in-browser TypeScript port (offline fallback)
 *
 * It defaults to the local dev server, so `npm run dev` talks to the backend
 * out of the box. Set `VITE_API_URL=""` to force the offline engine.
 *
 * Note the default uses 127.0.0.1 rather than `localhost`: on Windows
 * `localhost` resolves to ::1, and a backend started with
 * `uvicorn --host 127.0.0.1` binds IPv4 only, so the browser cannot reach it.
 * `backend/scripts/serve.py` binds both, but the literal IPv4 address works
 * regardless of how the server was started. See backend/CLAUDE.md.
 */
const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:8000'

export const client: RepurposeClient = API_URL ? httpClient(API_URL) : localClient
