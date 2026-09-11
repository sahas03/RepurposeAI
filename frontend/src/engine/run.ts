/**
 * run.ts
 * Orchestrates one full pipeline run and reports each stage as it completes.
 *
 * The computation is genuinely fast (a 200-gene x 150-drug matrix costs a few
 * milliseconds), so the cinematic stage sequence in the UI is *presentation*
 * layered over real work: each stage yields to the browser, records its true
 * wall-clock cost, and hands the UI its actual output. Nothing is faked, and
 * the real timings are surfaced in the HUD so the cost stays visible.
 */
import { buildCandidates, type SafetyTable } from './filters'
import { cosineReversalScore, weightedConnectivityScore, zscoreDiseaseSignature } from './scoring'
import type { Dataset, PipelineResult, PipelineSettings, ScoredDrug } from './types'
import {
  checkRecovery,
  hasRealValidationSignal,
  knownDrugSet,
  syntheticGroundTruth,
} from './validate'

export const STAGES = [
  {
    id: 'signature',
    index: '01',
    title: 'Disease Signature',
    short: 'SIGNATURE',
    desc: 'Load the differential-expression profile and harmonise gene identifiers.',
    detail:
      'Reads gene / logFC / p-value rows, upper-cases and de-duplicates symbols, then intersects them with the drug matrix index. On a real L1000 library this intersection is the bottleneck: only landmark genes survive it.',
  },
  {
    id: 'library',
    index: '02',
    title: 'Drug Library',
    short: 'LIBRARY',
    desc: 'Load the perturbation matrix of z-scored expression changes per compound.',
    detail:
      'Each column is one compound induced transcriptional change measured across the shared gene set. This matrix is the entire search space the reversal score sweeps.',
  },
  {
    id: 'reversal',
    index: '03',
    title: 'Signature Reversal',
    short: 'REVERSAL',
    desc: 'Score every compound by how strongly it mirrors the disease signature.',
    detail:
      'Cosine similarity between the z-scored disease vector and each drug column. A strongly negative score means the compound pushes expression in the opposite direction to the disease. WTCS is available as a CMap-style alternative.',
  },
  {
    id: 'safety',
    index: '04',
    title: 'Safety + Novelty',
    short: 'SCREEN',
    desc: 'Label known versus novel, and apply the Lipinski druglikeness proxy.',
    detail:
      'Novelty is labelled against a small hand-curated reference set, not a full indication database. Safety is Lipinski Rule of Five, a fast druglikeness proxy rather than ADMET modelling, and needs a structure descriptor table before it can activate.',
  },
  {
    id: 'explain',
    index: '05',
    title: 'Explainability',
    short: 'EXPLAIN',
    desc: 'Decompose each score into the genes that produced it.',
    detail:
      'The cosine score is a sum of per-gene products d_i x v_i. Ranking those products exposes exactly which genes a drug reverses and which it reinforces, so every score is auditable gene by gene.',
  },
  {
    id: 'validation',
    index: '06',
    title: 'Validation',
    short: 'VALIDATE',
    desc: 'Check whether the ranking recovers drugs already known to work.',
    detail:
      'A blind run should re-discover established treatments from expression math alone. On synthetic data the equivalent check is whether the planted reversal signals rank at the top while the planted reinforcing ones stay at the bottom.',
  },
] as const

export type StageId = (typeof STAGES)[number]['id']

export const METHOD_LABELS: Record<PipelineSettings['method'], string> = {
  cosine: 'Cosine similarity',
  'cosine-fast': 'Cosine similarity, vectorised fast path',
  wtcs: 'Weighted Connectivity Score (WTCS)',
}

/** Yield to the compositor so stage reveals paint at 60fps. */
const frame = () => new Promise<void>((r) => requestAnimationFrame(() => r()))

export interface StageReport {
  id: StageId
  ms: number
  /** Short, factual line describing what this stage actually produced. */
  readout: string
}

export async function runPipeline(
  dataset: Dataset,
  settings: PipelineSettings,
  safetyTable: SafetyTable | null,
  onStage: (report: StageReport) => void,
  /** Minimum time each stage is held on screen, for legibility. */
  dwellMs = 520,
): Promise<PipelineResult> {
  const timings: Record<string, number> = {}

  const stage = async <T>(id: StageId, readout: (v: T) => string, fn: () => T): Promise<T> => {
    const started = performance.now()
    const value = fn()
    const ms = performance.now() - started
    timings[id] = ms
    await frame()
    onStage({ id, ms, readout: readout(value) })
    const remaining = dwellMs - (performance.now() - started)
    if (remaining > 0) await new Promise((r) => setTimeout(r, remaining))
    return value
  }

  // 01 - disease signature
  const diseaseVec = await stage(
    'signature',
    () =>
      `${dataset.genes.length} genes harmonised from ${dataset.diseaseGenesBefore} differential-expression rows`,
    () => zscoreDiseaseSignature(dataset.disease.map((d) => d.logFC)),
  )

  // 02 - drug library
  await stage(
    'library',
    () => `${dataset.drugs.length} compound signatures loaded across ${dataset.genes.length} genes`,
    () => dataset.drugs.length,
  )

  // 03 - reversal scoring
  const allScores = await stage<ScoredDrug[]>(
    'reversal',
    (s) =>
      `strongest reversal ${s[0].reversalScore.toFixed(4)}, weakest ${s[s.length - 1].reversalScore.toFixed(4)}`,
    () =>
      settings.method === 'wtcs'
        ? weightedConnectivityScore(dataset)
        : cosineReversalScore(dataset, diseaseVec, settings.method === 'cosine-fast'),
  )

  // 04 - safety + novelty
  const known = knownDrugSet(settings.diseaseName)
  const poolN = Math.max(settings.displayTopN, settings.validationTopK, 20)
  const candidates = await stage(
    'safety',
    (c) =>
      safetyTable
        ? `${c.length} candidates screened, Lipinski proxy active`
        : `${c.length} candidates labelled, Lipinski proxy on standby (no structure table)`,
    () => buildCandidates(allScores, poolN, known, settings, safetyTable),
  )

  // 05 - explainability (per-candidate decomposition is computed on demand)
  await stage(
    'explain',
    () => `score decomposition available for all ${candidates.length} candidates`,
    () => candidates.length,
  )

  // 06 - validation
  const realSignal = hasRealValidationSignal(dataset.drugs, known)
  const { recovery, synthetic } = await stage(
    'validation',
    (v) =>
      v.recovery
        ? `${v.recovery.recoveredCount}/${v.recovery.referenceSetSize} known ${settings.diseaseName} drugs recovered in top ${settings.validationTopK}`
        : v.synthetic
          ? `${v.synthetic.recoveredCount}/${v.synthetic.plantedTotal} planted reversal signals recovered in top ${settings.validationTopK}`
          : 'no reference signal available in this dataset',
    () => ({
      recovery: realSignal
        ? checkRecovery(candidates, settings.diseaseName, settings.validationTopK)
        : null,
      synthetic: realSignal
        ? null
        : syntheticGroundTruth(candidates, dataset.drugs, settings.validationTopK),
    }),
  )

  return {
    settings,
    dataset: { id: dataset.id, label: dataset.label, provenance: dataset.provenance },
    methodLabel: METHOD_LABELS[settings.method],
    genesMatched: dataset.genes.length,
    drugsScored: dataset.drugs.length,
    allScores,
    candidates,
    recovery,
    synthetic,
    timings,
    safetyActive: safetyTable != null,
    diseaseVec,
    diseaseGenes: dataset.genes,
  }
}
