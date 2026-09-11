/**
 * validate.ts
 * Port of repurposeai/src/validate.py + app/validation_helpers.py.
 *
 * Two distinct checks, never conflated in the UI:
 *   - checkRecovery()          real known-drug recovery (needs real drug names)
 *   - syntheticGroundTruth()   planted-signal sanity check on the mock matrix
 */
import type { Candidate, RecoveryResult, SyntheticCheck } from './types'

/** Verbatim from validate.KNOWN_VALIDATION_SETS. */
export const KNOWN_VALIDATION_SETS: Record<string, string[]> = {
  'rheumatoid arthritis': [
    'baricitinib',
    'tofacitinib',
    'upadacitinib', // JAK inhibitors
    'etanercept',
    'adalimumab',
    'infliximab', // anti-TNF
    'tocilizumab',
    'sarilumab', // anti-IL6
    'methotrexate', // conventional DMARD
  ],
}

/** Drug-class grouping used only for display in the validation panel. */
export const DRUG_CLASSES: Record<string, string> = {
  baricitinib: 'JAK inhibitor',
  tofacitinib: 'JAK inhibitor',
  upadacitinib: 'JAK inhibitor',
  etanercept: 'anti-TNF biologic',
  adalimumab: 'anti-TNF biologic',
  infliximab: 'anti-TNF biologic',
  tocilizumab: 'anti-IL6 biologic',
  sarilumab: 'anti-IL6 biologic',
  methotrexate: 'conventional DMARD',
}

export const PLANTED_REVERSAL_PREFIX = 'planted_reversal_drug'
export const PLANTED_REINFORCING_PREFIX = 'planted_reinforcing_drug'

export function knownDrugSet(disease: string): Set<string> {
  return new Set(KNOWN_VALIDATION_SETS[disease.toLowerCase().trim()] ?? [])
}

/** True only if the drug library actually contains real reference drug names. */
export function hasRealValidationSignal(drugs: string[], known: Set<string>): boolean {
  const cols = new Set(drugs.map((d) => d.toLowerCase()))
  for (const d of known) if (cols.has(d)) return true
  return false
}

export function checkRecovery(
  ranked: Candidate[],
  diseaseName: string,
  topK: number,
): RecoveryResult {
  const reference = knownDrugSet(diseaseName)
  const top = ranked.slice(0, topK)
  const topNames = new Set(top.map((c) => c.drug.toLowerCase().trim()))
  const recovered = [...reference].filter((d) => topNames.has(d)).sort()

  return {
    disease: diseaseName,
    topK,
    referenceSetSize: reference.size,
    recoveredDrugs: recovered,
    recoveredCount: recovered.length,
    recoveryRate: reference.size ? recovered.length / reference.size : 0,
    novelCandidates: top
      .map((c) => c.drug)
      .filter((d) => !reference.has(d.toLowerCase().trim())),
  }
}

/**
 * Mock-data sanity check: do the planted reversal drugs land near the top and
 * the planted reinforcing (deliberately bad) drugs stay near the bottom?
 * Returns null when no planted naming convention is present.
 */
export function syntheticGroundTruth(
  ranked: Candidate[],
  allDrugs: string[],
  topK: number,
): SyntheticCheck | null {
  const reversalPlanted = allDrugs.filter((c) => c.startsWith(PLANTED_REVERSAL_PREFIX))
  const reinforcingPlanted = allDrugs.filter((c) => c.startsWith(PLANTED_REINFORCING_PREFIX))
  if (reversalPlanted.length === 0) return null

  const top = new Set(ranked.slice(0, topK).map((c) => c.drug))
  const recovered = reversalPlanted.filter((d) => top.has(d)).sort()

  return {
    recovered,
    recoveredCount: recovered.length,
    plantedTotal: reversalPlanted.length,
    recoveryRate: recovered.length / reversalPlanted.length,
    reinforcingPlanted,
    reinforcingRanks: ranked.filter((c) => reinforcingPlanted.includes(c.drug)),
  }
}

export function formatValidationStatement(r: RecoveryResult): string {
  if (r.recoveredCount === 0) {
    return `No known ${r.disease} drugs were recovered in the top ${r.topK} candidates — investigate signature quality before presenting novel candidates as high-confidence.`
  }
  return `Blind-ran on ${r.disease}: the pipeline surfaced ${r.recoveredCount}/${r.referenceSetSize} known effective treatments (${r.recoveredDrugs.join(', ')}) in the top ${r.topK} candidates, validating the method before surfacing ${r.novelCandidates.length} additional novel repurposing candidates.`
}
