import { create } from 'zustand'
import { client } from '@/api/client'
import type { StageId, StageReport } from '@/engine/run'
import { STAGES } from '@/engine/run'
import type { Dataset, PipelineResult, PipelineSettings } from '@/engine/types'
import { setEnergy } from './pointer'

export type Phase = 'idle' | 'loading' | 'running' | 'complete' | 'error'
export type StageState = 'pending' | 'active' | 'done' | 'error'

const initialStages = () =>
  Object.fromEntries(STAGES.map((s) => [s.id, 'pending'])) as Record<StageId, StageState>

export interface AppState {
  phase: Phase
  stages: Record<StageId, StageState>
  reports: Partial<Record<StageId, StageReport>>
  activeStage: StageId | null
  dataset: Dataset | null
  result: PipelineResult | null
  error: { stage: string; message: string } | null
  settings: PipelineSettings
  /** Candidate highlighted across the visualisations. */
  selected: string | null
  /** Candidate opened in the detail drawer. Kept separate from `selected`,
   *  which is set automatically after a run and must not pop a drawer open. */
  detail: string | null
  /** Stage id opened in the stage detail drawer. */
  openStage: StageId | null
  /** Gene focused in the reasoning graph. */
  focusGene: string | null
  candidateView: 'field' | 'list' | 'table'
  /** Diagnostics panel, revealed by the status-light easter egg. */
  diagnostics: boolean

  setSettings: (patch: Partial<PipelineSettings>) => void
  select: (drug: string | null) => void
  openDetail: (drug: string) => void
  closeDetail: () => void
  setOpenStage: (id: StageId | null) => void
  setFocusGene: (g: string | null) => void
  setCandidateView: (v: 'field' | 'list' | 'table') => void
  toggleDiagnostics: () => void
  /** Parse the dataset without scoring, so the data views are never empty. */
  preload: () => Promise<void>
  run: () => Promise<void>
  reset: () => void
}

export const DEFAULT_SETTINGS: PipelineSettings = {
  datasetId: 'synthetic-benchmark',
  diseaseName: 'rheumatoid arthritis',
  method: 'cosine-fast',
  displayTopN: 15,
  validationTopK: 20,
  weights: { reversal: 0.6, safety: 0.2, novelty: 0.2 },
}

export const useApp = create<AppState>((set, get) => ({
  phase: 'idle',
  stages: initialStages(),
  reports: {},
  activeStage: null,
  dataset: null,
  result: null,
  error: null,
  settings: DEFAULT_SETTINGS,
  selected: null,
  detail: null,
  openStage: null,
  focusGene: null,
  candidateView: 'field',
  diagnostics: false,

  setSettings: (patch) => set((s) => ({ settings: { ...s.settings, ...patch } })),
  select: (drug) => set({ selected: drug }),
  openDetail: (drug) => set({ selected: drug, detail: drug }),
  closeDetail: () => set({ detail: null }),
  setOpenStage: (id) => set({ openStage: id }),
  setFocusGene: (g) => set({ focusGene: g }),
  setCandidateView: (v) => set({ candidateView: v }),
  toggleDiagnostics: () => set((s) => ({ diagnostics: !s.diagnostics })),

  async preload() {
    if (get().dataset) return
    try {
      const dataset = await client.loadDataset(get().settings.datasetId)
      set({ dataset })
    } catch {
      // Silent: the sections fall back to their empty states, and the real
      // error surfaces properly when the user actually starts a run.
    }
  },

  reset: () =>
    set({
      phase: 'idle',
      stages: initialStages(),
      reports: {},
      activeStage: null,
      result: null,
      error: null,
      selected: null,
      detail: null,
      focusGene: null,
    }),

  async run() {
    const { settings } = get()
    set({
      phase: 'loading',
      stages: initialStages(),
      reports: {},
      activeStage: null,
      result: null,
      error: null,
      selected: null,
      detail: null,
    })
    setEnergy(0.45)

    try {
      const dataset = await client.loadDataset(settings.datasetId)
      set({ dataset, phase: 'running' })

      // Mark the first stage active before any work so the HUD never sits blank.
      set({ stages: { ...initialStages(), signature: 'active' }, activeStage: 'signature' })

      const order = STAGES.map((s) => s.id)
      const result = await client.run(dataset, settings, (report) => {
        setEnergy(0.55 + 0.45 * ((order.indexOf(report.id) + 1) / order.length))
        set((s) => {
          const stages = { ...s.stages, [report.id]: 'done' as StageState }
          const next = order[order.indexOf(report.id) + 1]
          if (next) stages[next] = 'active'
          return {
            stages,
            activeStage: next ?? null,
            reports: { ...s.reports, [report.id]: report },
          }
        })
      })

      set({
        result,
        phase: 'complete',
        activeStage: null,
        selected: result.candidates[0]?.drug ?? null,
      })
      // Settle back to an elevated ambient - the system stays "warm" post-run.
      setEnergy(0.34)
    } catch (e) {
      const active = get().activeStage
      const stage = STAGES.find((s) => s.id === active)?.title ?? 'Data load'
      set((s) => ({
        phase: 'error',
        error: { stage, message: e instanceof Error ? e.message : String(e) },
        stages: active ? { ...s.stages, [active]: 'error' } : s.stages,
      }))
      setEnergy(0)
    }
  },
}))

/** The candidate highlighted across the visualisations. */
export const useSelectedCandidate = () =>
  useApp((s) =>
    s.selected ? (s.result?.candidates.find((c) => c.drug === s.selected) ?? null) : null,
  )

/** The candidate whose detail drawer is open, if any. */
export const useDetailCandidate = () =>
  useApp((s) => (s.detail ? (s.result?.candidates.find((c) => c.drug === s.detail) ?? null) : null))
