import { useMemo, useState } from 'react'
import { cx } from '@/lib/cx'
import type { Dataset, PipelineResult } from '@/engine/types'
import { Hud } from '@/components/ui/Hud'

/**
 * The drug library as a constellation.
 *
 * Before scoring, each compound sits at a radius set by a real property of
 * its own data - the Euclidean norm of its expression column, i.e. how large
 * a transcriptional effect it has. After scoring, the field reorganises:
 * radius becomes reversal rank, so the strongest reversers are pulled to the
 * centre. That single transition is the clearest possible picture of what
 * the scoring stage did.
 *
 * 150 nodes at 60fps is achieved by transitioning `transform` on plain SVG
 * groups once, rather than animating anything per frame.
 */

const SIZE = 620
const C = SIZE / 2
const R_MAX = 268
const GOLDEN = 2.399963229728653

export interface ConstellationNode {
  drug: string
  angle: number
  norm: number
  /** Rank in the reversal ordering, or null before a run. */
  rank: number | null
  reversalScore: number | null
  isCandidate: boolean
  known: boolean
}

export function useConstellation(dataset: Dataset | null, result: PipelineResult | null) {
  return useMemo<ConstellationNode[]>(() => {
    if (!dataset) return []
    const nd = dataset.drugs.length
    const ng = dataset.genes.length

    // Column norms: a genuine measure of each compound's effect magnitude.
    const norms = new Float64Array(nd)
    for (let i = 0; i < ng; i++) {
      const row = i * nd
      for (let j = 0; j < nd; j++) norms[j] += dataset.matrix[row + j] ** 2
    }
    let maxNorm = 0
    for (let j = 0; j < nd; j++) {
      norms[j] = Math.sqrt(norms[j])
      if (norms[j] > maxNorm) maxNorm = norms[j]
    }

    const rankOf = new Map<string, number>()
    const scoreOf = new Map<string, number>()
    result?.allScores.forEach((s, i) => {
      rankOf.set(s.drug, i)
      scoreOf.set(s.drug, s.reversalScore)
    })
    const candidateSet = new Set(result?.candidates.map((c) => c.drug))
    const knownSet = new Set(result?.candidates.filter((c) => c.knownForDisease).map((c) => c.drug))

    return dataset.drugs.map((drug, j) => ({
      drug,
      angle: j * GOLDEN,
      norm: norms[j] / (maxNorm || 1),
      rank: rankOf.has(drug) ? rankOf.get(drug)! : null,
      reversalScore: scoreOf.get(drug) ?? null,
      isCandidate: candidateSet.has(drug),
      known: knownSet.has(drug),
    }))
  }, [dataset, result])
}

function position(n: ConstellationNode, total: number) {
  // Unscored: radius from effect magnitude. Scored: radius from reversal rank.
  const t = n.rank == null ? 0.34 + n.norm * 0.66 : 0.1 + (n.rank / Math.max(1, total - 1)) * 0.9
  const r = t * R_MAX
  return { x: C + Math.cos(n.angle) * r, y: C + Math.sin(n.angle) * r, t }
}

export function DrugConstellation({
  nodes,
  scored,
  selected,
  onSelect,
  className,
}: {
  nodes: ConstellationNode[]
  scored: boolean
  selected: string | null
  onSelect: (drug: string) => void
  className?: string
}) {
  const [hover, setHover] = useState<ConstellationNode | null>(null)
  const focus = hover ?? nodes.find((n) => n.drug === selected) ?? null

  return (
    <div className={cx('relative', className)}>
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        className="w-full"
        role="img"
        aria-label={
          scored
            ? 'Drug library constellation, arranged by reversal rank'
            : 'Drug library constellation, arranged by signature magnitude'
        }
        onMouseLeave={() => setHover(null)}
      >
        <defs>
          <radialGradient id="rpa-core">
            <stop offset="0%" stopColor="rgb(var(--c-mint))" stopOpacity="0.30" />
            <stop offset="70%" stopColor="rgb(var(--c-mint))" stopOpacity="0.05" />
            <stop offset="100%" stopColor="rgb(var(--c-mint))" stopOpacity="0" />
          </radialGradient>
        </defs>

        {/* orbital guides */}
        {[0.28, 0.52, 0.76, 1].map((f) => (
          <circle
            key={f}
            cx={C}
            cy={C}
            r={R_MAX * f}
            fill="none"
            stroke="rgb(var(--c-line) / 0.1)"
            strokeDasharray={f === 1 ? undefined : '2 6'}
          />
        ))}
        {/* radial spokes */}
        {Array.from({ length: 12 }, (_, i) => {
          const a = (i / 12) * Math.PI * 2
          return (
            <line
              key={i}
              x1={C + Math.cos(a) * 40}
              y1={C + Math.sin(a) * 40}
              x2={C + Math.cos(a) * R_MAX}
              y2={C + Math.sin(a) * R_MAX}
              stroke="rgb(var(--c-line) / 0.06)"
            />
          )
        })}

        <circle cx={C} cy={C} r={92} fill="url(#rpa-core)" />

        {/* the centre marker: what the whole field is being pulled toward */}
        <g>
          <circle
            cx={C}
            cy={C}
            r={30}
            fill="none"
            stroke="rgb(var(--c-mint) / 0.35)"
            strokeDasharray="3 4"
            className="origin-center animate-slow-spin"
            style={{ transformOrigin: `${C}px ${C}px` }}
          />
          <text
            x={C}
            y={C - 4}
            textAnchor="middle"
            className="fill-[rgb(var(--c-mint))] font-mono text-[8px] uppercase tracking-[0.2em]"
          >
            {scored ? 'strong' : 'disease'}
          </text>
          <text
            x={C}
            y={C + 8}
            textAnchor="middle"
            className="fill-[rgb(var(--c-mint))] font-mono text-[8px] uppercase tracking-[0.2em]"
          >
            {scored ? 'reversal' : 'signature'}
          </text>
        </g>

        {/* connections drawn only for the shortlist, so the pull is legible */}
        {scored &&
          nodes
            .filter((n) => n.isCandidate)
            .map((n) => {
              const p = position(n, nodes.length)
              return (
                <line
                  key={`l-${n.drug}`}
                  x1={C}
                  y1={C}
                  x2={p.x}
                  y2={p.y}
                  stroke="rgb(var(--c-mint) / 0.18)"
                  strokeWidth={n.drug === focus?.drug ? 1.4 : 0.7}
                  style={{ transition: 'all 1.4s cubic-bezier(0.22,1,0.36,1)' }}
                />
              )
            })}

        {nodes.map((n) => {
          const p = position(n, nodes.length)
          const isFocus = focus?.drug === n.drug
          const r = n.isCandidate ? (isFocus ? 8 : 5.4) : isFocus ? 6 : 2.9
          const fill = n.known
            ? 'rgb(var(--c-iris))'
            : n.isCandidate
              ? 'rgb(var(--c-mint))'
              : 'rgb(var(--c-chrome, var(--c-dim)))'
          return (
            <g
              key={n.drug}
              style={{
                transform: `translate(${p.x}px, ${p.y}px)`,
                transition: 'transform 1.5s cubic-bezier(0.22,1,0.36,1)',
              }}
            >
              {n.isCandidate && (
                <circle
                  r={r + 6}
                  fill="rgb(var(--c-mint) / 0.10)"
                  className={isFocus ? '' : 'animate-hud-blink'}
                />
              )}
              <circle
                r={r}
                fill={fill}
                fillOpacity={n.isCandidate ? 0.95 : 0.32 + n.norm * 0.3}
                stroke={isFocus ? 'rgb(var(--c-ink))' : 'none'}
                strokeWidth={1.2}
                style={{ transition: 'r 0.3s ease, fill-opacity 0.3s ease' }}
              />
              {/* generous invisible hit area - 3px dots are unhittable */}
              <circle
                r={11}
                fill="transparent"
                data-cursor="node"
                className="cursor-pointer"
                onMouseEnter={() => setHover(n)}
                onClick={() => onSelect(n.drug)}
              />
            </g>
          )
        })}
      </svg>

      {/* focus readout, anchored so the layout never shifts */}
      <div className="pointer-events-none absolute inset-x-0 bottom-0 flex justify-center">
        <div
          className={cx(
            'glass min-w-[280px] max-w-full rounded-lg border-line/16 px-4 py-3 transition-all duration-300',
            focus ? 'opacity-100' : 'translate-y-1 opacity-0',
          )}
        >
          {focus && (
            <>
              <div className="flex items-baseline justify-between gap-4">
                <span className="truncate font-mono text-[13px] font-medium text-ink">
                  {focus.drug}
                </span>
                {focus.rank != null && (
                  <span className="num shrink-0 text-[11px] text-mint">#{focus.rank + 1}</span>
                )}
              </div>
              <div className="mt-2 flex flex-wrap gap-x-5 gap-y-1">
                <span className="flex items-baseline gap-1.5">
                  <Hud>Magnitude</Hud>
                  <span className="num text-[11px] text-dim">{focus.norm.toFixed(3)}</span>
                </span>
                {focus.reversalScore != null && (
                  <span className="flex items-baseline gap-1.5">
                    <Hud>Reversal</Hud>
                    <span
                      className={cx(
                        'num text-[11px]',
                        focus.reversalScore < 0 ? 'text-mint' : 'text-ember',
                      )}
                    >
                      {focus.reversalScore.toFixed(4)}
                    </span>
                  </span>
                )}
              </div>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
