/**
 * http.ts
 * `RepurposeClient` over the FastAPI service in `backend/`.
 *
 * This is what makes the system have exactly ONE scoring engine. Every number
 * it returns was computed by `repurposeai/src/*.py` — the same functions the
 * Streamlit dashboard runs — rather than by the TypeScript port in
 * `src/engine/`. That port still exists (see the note at the bottom of
 * `client.ts`) but nothing in the live path calls it any more.
 *
 * Response shapes need no translation: `backend/repurpose_api/schemas.py`
 * mirrors `src/engine/types.ts` field-for-field in camelCase, which
 * `backend/scripts/check_frontend_parity.py` verifies field by field.
 *
 * Two deliberate choices:
 *
 *   `loadDataset()` still parses the CSVs in `public/data/` client-side. The
 *   backend does not ship the drug matrix over the wire, and the UI genuinely
 *   needs it — the reversal mirror and the explain graph read `dataset.matrix`
 *   directly. Keeping the parse local also means the data views still populate
 *   when the backend is down.
 *
 *   `run()` uses Server-Sent Events, not a single POST. The UI's discovery
 *   sequence is driven by `onStage`, and the SSE endpoint emits each stage as
 *   it genuinely completes with its real wall-clock cost. A blocking POST
 *   would leave `onStage` silent and flatten that sequence into a spinner.
 */
import type { DatasetDescriptor, RepurposeClient } from './client'
import { DATASETS, localClient } from './client'
import type { StageId, StageReport } from '@/engine/run'
import type { GeneContribution, PipelineResult, PipelineSettings } from '@/engine/types'

/** Shape of one `event: stage` frame. Mirrors `streaming.py::_stage_payload`. */
interface StageEvent {
  id: StageId
  ms: number
  readout: string
  index: number
  total: number
}

/** Shape of one `event: error` frame, and of the JSON error envelope. */
interface ApiError {
  stage: string
  type: string
  message: string
}

export class BackendUnreachableError extends Error {
  readonly baseUrl: string

  constructor(baseUrl: string) {
    super(
      `Cannot reach the RepurposeAI API at ${baseUrl}. ` +
        'Start it with:  python backend/scripts/serve.py',
    )
    this.name = 'BackendUnreachableError'
    this.baseUrl = baseUrl
  }
}

/** Strip one trailing slash so `${base}/api/...` never doubles up. */
function normalise(baseUrl: string): string {
  return baseUrl.replace(/\/+$/, '')
}

function settingsToQuery(settings: PipelineSettings): string {
  return new URLSearchParams({
    datasetId: settings.datasetId,
    diseaseName: settings.diseaseName,
    method: settings.method,
    displayTopN: String(settings.displayTopN),
    validationTopK: String(settings.validationTopK),
    weightReversal: String(settings.weights.reversal),
    weightSafety: String(settings.weights.safety),
    weightNovelty: String(settings.weights.novelty),
  }).toString()
}

/** Pull a useful sentence out of the backend's structured error envelope. */
async function readError(res: Response, fallback: string): Promise<string> {
  try {
    const body = (await res.json()) as { error?: ApiError }
    if (body.error?.message) return body.error.message
  } catch {
    /* not JSON — fall through */
  }
  return `${fallback} (HTTP ${res.status}).`
}

export function httpClient(baseUrl: string): RepurposeClient {
  const base = normalise(baseUrl)

  return {
    // Static, and identical to what GET /api/datasets returns. The interface is
    // synchronous, and the descriptors are compile-time constants on both
    // sides, so there is nothing to await here.
    listDatasets: (): DatasetDescriptor[] => DATASETS,

    // Parsed in-page, on purpose — see the module comment.
    loadDataset: (id: string) => localClient.loadDataset(id),

    run(_dataset, settings, onStage): Promise<PipelineResult> {
      const url = `${base}/api/run/stream?${settingsToQuery(settings)}`

      return new Promise<PipelineResult>((resolve, reject) => {
        const source = new EventSource(url)
        let settled = false

        /** EventSource reconnects on a closed socket; without this it would
         *  silently start a brand new pipeline run every few seconds. */
        const finish = (fn: () => void) => {
          if (settled) return
          settled = true
          source.close()
          fn()
        }

        source.addEventListener('stage', (e) => {
          const stage = JSON.parse((e as MessageEvent).data) as StageEvent
          onStage({ id: stage.id, ms: stage.ms, readout: stage.readout } satisfies StageReport)
        })

        source.addEventListener('result', (e) => {
          const result = JSON.parse((e as MessageEvent).data) as PipelineResult
          finish(() => resolve(result))
        })

        source.addEventListener('error', (e) => {
          // A stage genuinely failed server-side, and said which one.
          const data = (e as MessageEvent).data
          if (typeof data === 'string' && data.length > 0) {
            const err = JSON.parse(data) as ApiError
            finish(() => reject(new Error(`${err.message} (stage: ${err.stage})`)))
            return
          }
          // No payload: the connection itself failed. The usual cause is that
          // nobody started the server.
          finish(() => reject(new BackendUnreachableError(base)))
        })
      })
    },

    async explain(datasetId, drug, topN): Promise<GeneContribution[]> {
      const query = new URLSearchParams({ datasetId, topNGenes: String(topN) })
      const url = `${base}/api/candidates/${encodeURIComponent(drug)}/explain?${query}`

      let res: Response
      try {
        res = await fetch(url)
      } catch {
        throw new BackendUnreachableError(base)
      }
      if (!res.ok) {
        throw new Error(await readError(res, `Could not explain ${drug}`))
      }
      const body = (await res.json()) as { topGenes: GeneContribution[] }
      return body.topGenes
    },
  }
}
