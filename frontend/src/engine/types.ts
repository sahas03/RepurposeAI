/**
 * Shared shapes for the scoring engine.
 *
 * These mirror the DataFrame columns produced by the Python pipeline in
 * `repurposeai/src/*.py` one-for-one, so a future backend can return this
 * JSON directly and the UI needs no changes. See `src/api/client.ts`.
 */

export interface DiseaseGene {
  gene: string
  logFC: number
  pvalue: number
}

/** Disease signature + drug perturbation matrix, restricted to shared genes. */
export interface Dataset {
  id: string
  label: string
  /** How the data should be described to a viewer. Never inflate this. */
  provenance: 'synthetic' | 'real' | 'uploaded'
  disease: DiseaseGene[]
  /** Gene symbols, row order of `matrix`. */
  genes: string[]
  /** Drug identifiers, column order of `matrix`. */
  drugs: string[]
  /** genes x drugs, z-scored differential expression. Row-major. */
  matrix: Float64Array
  /** Rows dropped by gene harmonisation, for honest reporting. */
  diseaseGenesBefore: number
  drugsBefore: number
}

export interface ScoredDrug {
  drug: string
  /** Cosine similarity or WTCS. More negative = stronger reversal. */
  reversalScore: number
}

export interface Candidate extends ScoredDrug {
  rank: number
  knownForDisease: boolean
  noveltyLabel: 'known hit (validation evidence)' | 'novel candidate'
  /** 0..1 Lipinski proxy. `null` when no structure table is loaded. */
  safetyScore: number | null
  /** Reversal component after inversion + min-max scaling to [0,1]. */
  reversalScaled: number
  noveltyBonus: number
  finalScore: number
  finalRank: number
}

export interface GeneContribution {
  gene: string
  diseaseLogFC: number
  drugZscore: number
  contribution: number
  direction: 'reversed by drug' | 'reinforced by drug (unwanted)'
}

export interface RecoveryResult {
  disease: string
  topK: number
  referenceSetSize: number
  recoveredDrugs: string[]
  recoveredCount: number
  recoveryRate: number
  novelCandidates: string[]
}

export interface SyntheticCheck {
  recovered: string[]
  recoveredCount: number
  plantedTotal: number
  recoveryRate: number
  reinforcingPlanted: string[]
  reinforcingRanks: Candidate[]
}

export type ScoringMethod = 'cosine' | 'cosine-fast' | 'wtcs'

export interface PipelineSettings {
  datasetId: string
  diseaseName: string
  method: ScoringMethod
  displayTopN: number
  validationTopK: number
  weights: { reversal: number; safety: number; novelty: number }
}

export interface PipelineResult {
  settings: PipelineSettings
  dataset: Pick<Dataset, 'id' | 'label' | 'provenance'>
  methodLabel: string
  genesMatched: number
  drugsScored: number
  /** Every drug, ascending by reversal score. Used by the constellation. */
  allScores: ScoredDrug[]
  candidates: Candidate[]
  recovery: RecoveryResult | null
  synthetic: SyntheticCheck | null
  /** Per-stage wall-clock cost of the real computation, in ms. */
  timings: Record<string, number>
  safetyActive: boolean
  diseaseVec: Float64Array
  diseaseGenes: string[]
}
