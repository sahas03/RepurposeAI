import { motion, useReducedMotion } from 'framer-motion'
import { cx } from '@/lib/cx'
import type { Candidate } from '@/engine/types'

/**
 * The shortlist as a therapeutic field.
 *
 * Rank one sits at the centre and the rest spiral outward, so strength is
 * read as proximity rather than as a row number. Nodes emerge one at a time,
 * strongest first, which is the reveal moment at the end of a run.
 */
const SIZE = 620
const C = SIZE / 2
const GOLDEN = 2.399963229728653

export function CandidateField({
  candidates,
  selected,
  onSelect,
}: {
  candidates: Candidate[]
  selected: string | null
  onSelect: (drug: string) => void
}) {
  const reduced = useReducedMotion()
  const n = candidates.length
  const scores = candidates.map((c) => c.finalScore)
  const min = Math.min(...scores)
  const max = Math.max(...scores)

  const place = (i: number) => {
    if (i === 0) return { x: C, y: C, r: 34 }
    // Spiral outward; radius grows with the square root so the ring density
    // stays even instead of crowding the middle.
    const t = i / Math.max(1, n - 1)
    const radius = 78 + Math.sqrt(t) * 200
    const a = i * GOLDEN
    const rel = (candidates[i].finalScore - min) / (max - min || 1)
    return { x: C + Math.cos(a) * radius, y: C + Math.sin(a) * radius, r: 10 + rel * 12 }
  }

  return (
    <div className="relative">
      <svg
        viewBox={`0 0 ${SIZE} ${SIZE}`}
        className="w-full"
        role="img"
        aria-label={`${n} therapeutic candidates, ranked`}
      >
        <defs>
          <radialGradient id="rpa-lead">
            <stop offset="0%" stopColor="rgb(var(--c-mint))" stopOpacity="0.35" />
            <stop offset="100%" stopColor="rgb(var(--c-mint))" stopOpacity="0" />
          </radialGradient>
        </defs>

        {[100, 170, 240, 290].map((r) => (
          <circle
            key={r}
            cx={C}
            cy={C}
            r={r}
            fill="none"
            stroke="rgb(var(--c-line) / 0.09)"
            strokeDasharray="2 7"
          />
        ))}
        <circle cx={C} cy={C} r={120} fill="url(#rpa-lead)" />

        {/* links from the lead candidate outward */}
        {candidates.slice(1).map((c, i) => {
          const p = place(i + 1)
          return (
            <motion.line
              key={`l-${c.drug}`}
              x1={C}
              y1={C}
              x2={p.x}
              y2={p.y}
              stroke="rgb(var(--c-mint) / 0.12)"
              initial={reduced ? false : { pathLength: 0, opacity: 0 }}
              whileInView={{ pathLength: 1, opacity: 1 }}
              viewport={{ once: true }}
              transition={{ duration: 0.7, delay: 0.5 + i * 0.055, ease: [0.22, 1, 0.36, 1] }}
            />
          )
        })}

        {candidates.map((c, i) => {
          const p = place(i)
          const on = selected === c.drug
          const lead = i === 0
          return (
            <motion.g
              key={c.drug}
              className="cursor-pointer"
              data-cursor="node"
              onClick={() => onSelect(c.drug)}
              initial={reduced ? false : { opacity: 0, scale: 0.2 }}
              whileInView={{ opacity: 1, scale: 1 }}
              viewport={{ once: true }}
              transition={{
                // Strongest first: the reveal order is the ranking.
                delay: i * 0.09,
                duration: 0.65,
                ease: [0.22, 1, 0.36, 1],
              }}
              style={{ transformOrigin: `${p.x}px ${p.y}px` }}
            >
              {(lead || on) && (
                <circle
                  cx={p.x}
                  cy={p.y}
                  r={p.r + 12}
                  fill="none"
                  stroke="rgb(var(--c-mint) / 0.35)"
                  strokeDasharray="3 4"
                  className="animate-slow-spin"
                  style={{ transformOrigin: `${p.x}px ${p.y}px` }}
                />
              )}
              <circle
                cx={p.x}
                cy={p.y}
                r={p.r}
                fill={
                  c.knownForDisease
                    ? 'rgb(var(--c-iris) / 0.9)'
                    : lead
                      ? 'rgb(var(--c-mint) / 0.95)'
                      : 'rgb(var(--c-mint) / 0.55)'
                }
                stroke={on ? 'rgb(var(--c-ink))' : 'rgb(var(--c-mint) / 0.5)'}
                strokeWidth={on ? 1.8 : 1}
                className="transition-all duration-300 hover:brightness-125"
              />
              <text
                x={p.x}
                y={p.y + 4}
                textAnchor="middle"
                className={cx(
                  'pointer-events-none font-mono font-semibold',
                  lead ? 'text-[13px]' : 'text-[10px]',
                )}
                fill="rgb(var(--c-base))"
              >
                {c.finalRank}
              </text>
              {(lead || on) && (
                <text
                  x={p.x}
                  y={p.y + p.r + 20}
                  textAnchor="middle"
                  className="pointer-events-none fill-[rgb(var(--c-ink))] font-mono text-[10px]"
                >
                  {c.drug}
                </text>
              )}
            </motion.g>
          )
        })}
      </svg>

      <div className="pointer-events-none absolute left-4 top-4">
        <span className="font-mono text-[9px] uppercase tracking-hud text-faint">
          Centre = highest fused score
        </span>
      </div>
    </div>
  )
}
