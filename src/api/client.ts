/**
 * client.ts
 * The single seam between the UI and the pipeline.
 *
 * Today the pipeline runs in the browser against the CSVs in public/data,
 * using a line-by-line port of the Python modules (see src/engine). When the
 * Python backend is wired up, implement `RepurposeClient` over HTTP and swap
 * the export at the bottom of this file. No component imports the engine
 * directly, so nothing above this layer has to change.
 */
import type { SafetyTable } from '@/engine/filters'
import { harmonize, parseDiseaseSignature, parseL1000Matrix } from '@/engine/loader'
import { runPipeline, type StageReport } from '@/engine/run'
import type { Dataset, PipelineResult, PipelineSettings } from '@/engine/types'

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
 * Backend integration point.
 *
 * Replace the export below with an HTTP implementation once the Python
 * service exposes the pipeline. The response shapes it must return are the
 * exported interfaces in src/engine/types.ts, which mirror the DataFrame
 * columns the Python already produces.
 *
 *   export const client: RepurposeClient = httpClient(import.meta.env.VITE_API_URL)
 */
export const client: RepurposeClient = localClient
