/**
 * useExplain.ts
 * Per-candidate gene decomposition, fetched from the backend.
 *
 * This replaces the direct `topContributingGenes()` calls that
 * `ExplainSection` and `CandidateDetail` used to make into `src/engine/`.
 * Those were synchronous and instant; a real API call is neither, so this hook
 * carries the two states a network round trip introduces and an in-page
 * function call never had: `loading` and `error`.
 *
 * The cached result is tagged with the drug (and topN) it was fetched for, and
 * `loading` is *derived* by comparing that tag against what the caller is
 * asking for now. That matters for more than tidiness: holding the previous
 * drug's genes while a new drug loads would render one compound's numbers
 * under another compound's name, which is precisely the kind of invented
 * number the project's honesty rules exist to prevent. Deriving instead means
 * the component can never be handed mismatched data.
 */
import { useEffect, useState } from 'react'
import { client } from './client'
import type { GeneContribution } from '@/engine/types'

export interface ExplainState {
  genes: GeneContribution[]
  loading: boolean
  /** Human-readable, already suitable for display. Null when fine. */
  error: string | null
}

/** What was fetched, and what it was fetched for. */
interface Cached {
  key: string | null
  genes: GeneContribution[]
  error: string | null
}

const IDLE: ExplainState = { genes: [], loading: false, error: null }
const PENDING: ExplainState = { genes: [], loading: true, error: null }

export function useExplain(
  datasetId: string | null,
  drug: string | null,
  topN: number,
): ExplainState {
  const [cached, setCached] = useState<Cached>({ key: null, genes: [], error: null })
  const key = datasetId && drug ? `${datasetId}|${drug}|${topN}` : null

  useEffect(() => {
    if (!datasetId || !drug || !key) return

    // Guards against a slow response for a previously-selected drug landing
    // after a faster one for the current drug, and overwriting it.
    let current = true

    client
      .explain(datasetId, drug, topN)
      .then((genes) => {
        if (current) setCached({ key, genes, error: null })
      })
      .catch((e: unknown) => {
        if (current) {
          setCached({ key, genes: [], error: e instanceof Error ? e.message : String(e) })
        }
      })

    return () => {
      current = false
    }
  }, [datasetId, drug, topN, key])

  if (!key) return IDLE
  // The cache belongs to a different request than the one being asked for, so
  // the current one is still in flight.
  if (cached.key !== key) return PENDING
  return { genes: cached.genes, loading: false, error: cached.error }
}
