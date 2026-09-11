/**
 * filters.ts
 * Port of repurposeai/src/filters.py - novelty labelling and score fusion.
 *
 * The Lipinski safety screen is *structurally* ported (the four rules and the
 * approved-drug bonus are identical), but computing MW / logP / HBD / HBA from
 * a SMILES string needs a cheminformatics toolkit (RDKit) that does not exist
 * in the browser. So this module scores from a pre-computed descriptor table
 * when one is supplied and otherwise reports the screen as inactive - exactly
 * what the Python does when data/raw/smiles_lookup.csv is missing.
 */
import type { Candidate, PipelineSettings, ScoredDrug } from './types'

export interface Descriptors {
  mw: number
  logp: number
  hbd: number
  hba: number
}

/** Port of lipinski_safety_score(): fraction of the four rules passed. */
export function lipinskiSafetyScore(d: Descriptors): number {
  const checks = [d.mw <= 500, d.logp <= 5, d.hbd <= 5, d.hba <= 10]
  return checks.filter(Boolean).length / checks.length
}

export interface SafetyTable {
  descriptors: Record<string, Descriptors>
  approved?: Set<string>
}

function safetyFor(drug: string, table: SafetyTable | null): number | null {
  if (!table) return null
  const d = table.descriptors[drug]
  if (!d) return 0.5 // unknown structure -> neutral, flagged for manual review
  let score = lipinskiSafetyScore(d)
  if (table.approved?.has(drug)) score = Math.min(1, score + 0.2)
  return score
}

/**
 * Port of rank_candidates() + apply_novelty_filter() + combine_scores(),
 * run as one pass because the UI always needs all three together.
 */
export function buildCandidates(
  scores: ScoredDrug[],
  poolN: number,
  knownDrugs: Set<string>,
  settings: PipelineSettings,
  safetyTable: SafetyTable | null,
): Candidate[] {
  const pool = scores.slice(0, poolN)
  if (pool.length === 0) return []

  const rs = pool.map((p) => p.reversalScore)
  const rMax = Math.max(...rs)
  const rMin = Math.min(...rs)
  const { reversal, safety, novelty } = settings.weights

  const rows = pool.map((p, i) => {
    const knownForDisease = knownDrugs.has(p.drug.toLowerCase().trim())
    // invert so that "more negative" maps towards 1
    const reversalScaled = (rMax - p.reversalScore) / (rMax - rMin + 1e-9)
    const noveltyBonus = knownForDisease ? 1.0 : 0.6
    const safetyScore = safetyFor(p.drug, safetyTable)
    const finalScore =
      reversal * reversalScaled + safety * (safetyScore ?? 0.5) + novelty * noveltyBonus

    return {
      drug: p.drug,
      reversalScore: p.reversalScore,
      rank: i + 1,
      knownForDisease,
      noveltyLabel: knownForDisease
        ? ('known hit (validation evidence)' as const)
        : ('novel candidate' as const),
      safetyScore,
      reversalScaled,
      noveltyBonus,
      finalScore,
      finalRank: 0,
    }
  })

  rows.sort((a, b) => b.finalScore - a.finalScore)
  rows.forEach((r, i) => (r.finalRank = i + 1))
  return rows
}
