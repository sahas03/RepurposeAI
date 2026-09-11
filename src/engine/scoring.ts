/**
 * scoring.ts
 * Direct port of repurposeai/src/signature_matching.py.
 *
 * Kept deliberately literal - variable names and the order of operations
 * follow the Python so the two can be diffed by eye when the backend lands.
 */
import type { Dataset, ScoredDrug } from './types'

/** Column `j` of a row-major genes x drugs matrix. */
function drugColumn(ds: Dataset, j: number): Float64Array {
  const n = ds.genes.length
  const nd = ds.drugs.length
  const out = new Float64Array(n)
  for (let i = 0; i < n; i++) out[i] = ds.matrix[i * nd + j]
  return out
}

/** z = (x - mean) / std(ddof=0), matching zscore_disease_signature(). */
export function zscoreDiseaseSignature(logFC: number[]): Float64Array {
  const n = logFC.length
  let mean = 0
  for (const v of logFC) mean += v
  mean /= n
  let varSum = 0
  for (const v of logFC) varSum += (v - mean) ** 2
  const std = Math.sqrt(varSum / n)
  const out = new Float64Array(n)
  for (let i = 0; i < n; i++) out[i] = std === 0 ? 0 : (logFC[i] - mean) / std
  return out
}

/**
 * Cosine similarity between the disease vector and every drug column.
 * Strongly NEGATIVE = the drug mirrors the disease signature = candidate.
 *
 * `fast` is the vectorised path from app/fast_scoring.py. Same math, one
 * pass over the matrix instead of a per-drug slice, so it stays honest to
 * expose it as a toggle rather than a silent replacement.
 */
export function cosineReversalScore(
  ds: Dataset,
  diseaseVec: Float64Array,
  fast: boolean,
): ScoredDrug[] {
  const nGenes = ds.genes.length
  const nDrugs = ds.drugs.length

  let dNorm = 0
  for (const v of diseaseVec) dNorm += v * v
  dNorm = Math.sqrt(dNorm)
  if (dNorm === 0) throw new Error('Disease vector has zero norm; check input signature.')

  const scores = new Float64Array(nDrugs)

  if (fast) {
    // Single streaming pass: accumulate dot products and column norms together.
    const dots = new Float64Array(nDrugs)
    const norms = new Float64Array(nDrugs)
    for (let i = 0; i < nGenes; i++) {
      const di = diseaseVec[i]
      const row = i * nDrugs
      for (let j = 0; j < nDrugs; j++) {
        const v = ds.matrix[row + j]
        dots[j] += di * v
        norms[j] += v * v
      }
    }
    for (let j = 0; j < nDrugs; j++) {
      const vn = Math.sqrt(norms[j])
      scores[j] = vn === 0 ? 0 : dots[j] / (dNorm * vn)
    }
  } else {
    for (let j = 0; j < nDrugs; j++) {
      const col = drugColumn(ds, j)
      let dot = 0
      let vn = 0
      for (let i = 0; i < nGenes; i++) {
        dot += diseaseVec[i] * col[i]
        vn += col[i] * col[i]
      }
      vn = Math.sqrt(vn)
      scores[j] = vn === 0 ? 0 : dot / (dNorm * vn)
    }
  }

  return ds.drugs
    .map((drug, j) => ({ drug, reversalScore: scores[j] }))
    .sort((a, b) => a.reversalScore - b.reversalScore)
}

/** pandas Series.rank(ascending=False) with average ties. rank 1 = largest. */
function rankDescending(values: Float64Array): Float64Array {
  const n = values.length
  const idx = Array.from({ length: n }, (_, i) => i).sort((a, b) => values[b] - values[a])
  const ranks = new Float64Array(n)
  let i = 0
  while (i < n) {
    let j = i
    while (j + 1 < n && values[idx[j + 1]] === values[idx[i]]) j++
    const avg = (i + j + 2) / 2 // 1-based average of the tied block
    for (let k = i; k <= j; k++) ranks[idx[k]] = avg
    i = j + 1
  }
  return ranks
}

/** Simplified running-sum enrichment score, port of _enrichment_score(). */
function enrichmentScore(ranked: Float64Array, memberIdx: number[], n: number): number {
  if (memberIdx.length === 0) return 0
  const positions = memberIdx.map((i) => ranked[i] / n).sort((x, y) => x - y)
  const k = positions.length
  let a = -Infinity
  let b = -Infinity
  for (let i = 0; i < k; i++) {
    a = Math.max(a, (i + 1) / k - positions[i])
    b = Math.max(b, positions[i] - i / k)
  }
  return a > b ? a : -b
}

/**
 * Simplified Weighted Connectivity Score, port of weighted_connectivity_score().
 * Splits the disease signature into up/down gene sets and measures how each
 * drug's ranked profile enriches for them in the *opposite* direction.
 */
export function weightedConnectivityScore(
  ds: Dataset,
  upThresh = 1.0,
  downThresh = -1.0,
): ScoredDrug[] {
  const upIdx: number[] = []
  const downIdx: number[] = []
  ds.disease.forEach((g, i) => {
    if (g.logFC >= upThresh) upIdx.push(i)
    else if (g.logFC <= downThresh) downIdx.push(i)
  })

  if (upIdx.length === 0 || downIdx.length === 0) {
    throw new Error(
      `Thresholds too strict: ${upIdx.length} up genes, ${downIdx.length} down genes. ` +
        'Loosen the up/down thresholds.',
    )
  }

  const n = ds.genes.length
  const out: ScoredDrug[] = []
  for (let j = 0; j < ds.drugs.length; j++) {
    const ranked = rankDescending(drugColumn(ds, j))
    const esUp = enrichmentScore(ranked, upIdx, n)
    const esDown = enrichmentScore(ranked, downIdx, n)
    // Reversal: disease-up genes should be pushed DOWN by the drug and
    // vice-versa, i.e. the two enrichment scores must disagree in sign.
    const wtcs = Math.sign(esUp) !== Math.sign(esDown) ? (esUp - esDown) / 2 : 0
    out.push({ drug: ds.drugs[j], reversalScore: wtcs })
  }
  return out.sort((a, b) => a.reversalScore - b.reversalScore)
}

/** Port of top_contributing_genes(): contribution_i = d_i * v_i. */
export function topContributingGenes(ds: Dataset, diseaseVec: Float64Array, drug: string, topN = 10) {
  const j = ds.drugs.indexOf(drug)
  if (j < 0) return []
  const nd = ds.drugs.length
  return ds.genes
    .map((gene, i) => {
      const drugZscore = ds.matrix[i * nd + j]
      const diseaseLogFC = diseaseVec[i]
      const contribution = diseaseLogFC * drugZscore
      return {
        gene,
        diseaseLogFC,
        drugZscore,
        contribution,
        direction:
          contribution < 0
            ? ('reversed by drug' as const)
            : ('reinforced by drug (unwanted)' as const),
      }
    })
    .sort((a, b) => a.contribution - b.contribution)
    .slice(0, topN)
}
