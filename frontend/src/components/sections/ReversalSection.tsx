import { useMemo, useState } from 'react'
import { cx } from '@/lib/cx'
import { zscoreDiseaseSignature } from '@/engine/scoring'
import { GlassPanel, SectionHead } from '@/components/ui/GlassPanel'
import { AnimatedNumber, Hud, Provenance } from '@/components/ui/Hud'
import { Reveal } from '@/components/ui/Reveal'
import { useApp } from '@/store/useApp'
import { EmptyField } from './SignatureSection'

/**
 * Signature reversal, drawn as the mirror it actually is.
 *
 * Genes run left to right ordered by their disease z-score. The disease
 * signal is drawn upward from the axis; the selected compound's signal is
 * drawn downward. A strong reversal candidate produces a near mirror image
 * across that axis, and a reinforcing compound produces a shadow of the same
 * shape on the same side. The cosine score is literally the alignment of
 * those two shapes, so the number and the picture cannot disagree.
 */

const W = 900
const H = 300
const MID = H / 2

export function ReversalSection() {
  const dataset = useApp((s) => s.dataset)
  const result = useApp((s) => s.result)
  const [pick, setPick] = useState<string | null>(null)

  const diseaseVec = useMemo(() => {
    // After a run this is the backend's vector, computed by the Python.
    if (result) return result.diseaseVec
    // Before a run there is nothing to ask the backend for: preload() parses
    // the CSVs without scoring, precisely so this view is not empty, and the
    // API has no endpoint that z-scores a signature without running the whole
    // pipeline. This is therefore the ONE place the TS engine still executes
    // in the live path -- a preview that the first real run replaces.
    if (!dataset) return null
    return zscoreDiseaseSignature(dataset.disease.map((d) => d.logFC))
  }, [dataset, result])

  /** Top candidates plus the worst reinforcer, which is the negative control. */
  const options = useMemo(() => {
    if (!result) return []
    const best = result.allScores.slice(0, 6).map((s) => ({ ...s, control: false }))
    const worst = result.allScores[result.allScores.length - 1]
    return [...best, { ...worst, control: true }]
  }, [result])

  const active = pick ?? options[0]?.drug ?? null

  const view = useMemo(() => {
    if (!dataset || !diseaseVec || !active) return null
    const j = dataset.drugs.indexOf(active)
    if (j < 0) return null
    const nd = dataset.drugs.length

    const rows = dataset.genes.map((gene, i) => ({
      gene,
      d: diseaseVec[i],
      v: dataset.matrix[i * nd + j],
    }))
    rows.sort((a, b) => b.d - a.d)

    const maxD = Math.max(...rows.map((r) => Math.abs(r.d))) || 1
    const maxV = Math.max(...rows.map((r) => Math.abs(r.v))) || 1

    // Recompute cosine here from the same rows the chart draws, so the number
    // on screen is provably the number the picture describes.
    let dot = 0
    let nd2 = 0
    let nv2 = 0
    for (const r of rows) {
      dot += r.d * r.v
      nd2 += r.d * r.d
      nv2 += r.v * r.v
    }
    const cosine = dot / (Math.sqrt(nd2) * Math.sqrt(nv2) || 1)
    const reversedCount = rows.filter((r) => r.d * r.v < 0).length

    return { rows, maxD, maxV, cosine, reversedCount }
  }, [dataset, diseaseVec, active])

  return (
    <section id="reversal" className="relative px-5 py-28 sm:px-8">
      <div className="mx-auto w-full max-w-[1400px]">
        <Reveal>
          <SectionHead
            index="04"
            eyebrow="Stage 03 · the core idea"
            title="Find the compound that writes the opposite."
            lede="The disease pushes genes up and down. A useful drug pushes the same genes the other way. Cosine similarity measures exactly how well those two shapes mirror each other — and a strongly negative score is the whole thesis of this project."
          />
        </Reveal>

        {!result || !view ? (
          <EmptyField
            label="No reversal scores yet"
            hint="This view compares the disease signature against a scored compound. Initiate discovery to populate it."
          />
        ) : (
          <div className="space-y-5">
            <Reveal>
              <div className="flex flex-wrap items-center gap-2">
                <Hud className="mr-1">Compare against</Hud>
                {options.map((o) => (
                  <button
                    key={o.drug}
                    data-cursor="button"
                    onClick={() => setPick(o.drug)}
                    className={cx(
                      'rounded-md border px-3 py-1.5 font-mono text-[11px] transition-all duration-300',
                      active === o.drug
                        ? o.control
                          ? 'border-ember/60 bg-ember/10 text-ember'
                          : 'border-mint/60 bg-mint/10 text-mint'
                        : 'border-line/16 text-dim hover:border-line/35 hover:text-ink',
                    )}
                  >
                    {o.control && <span className="mr-1.5 opacity-70">control ·</span>}
                    {o.drug}
                  </button>
                ))}
              </div>
            </Reveal>

            <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_300px]">
              <Reveal>
                <GlassPanel kind="primary" ticks className="overflow-hidden p-4 sm:p-6">
                  <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                    <div className="flex items-center gap-2">
                      <span className="h-2.5 w-2.5 rounded-sm bg-ember" />
                      <Hud>Disease signal</Hud>
                    </div>
                    <Hud className="text-faint">
                      {view.rows.length} genes, sorted by disease z-score
                    </Hud>
                    <div className="flex items-center gap-2">
                      <span
                        className={cx(
                          'h-2.5 w-2.5 rounded-sm',
                          view.cosine < 0 ? 'bg-mint' : 'bg-ember',
                        )}
                      />
                      <Hud>Compound signal</Hud>
                    </div>
                  </div>

                  <svg
                    viewBox={`0 0 ${W} ${H}`}
                    className="w-full"
                    role="img"
                    aria-label={`Disease signature compared with ${active}, cosine ${view.cosine.toFixed(3)}`}
                  >
                    {/* axis and guides */}
                    <line
                      x1="0"
                      y1={MID}
                      x2={W}
                      y2={MID}
                      stroke="rgb(var(--c-line) / 0.35)"
                      strokeWidth="1"
                    />
                    {[0.25, 0.5, 0.75].map((f) => (
                      <g key={f}>
                        <line
                          x1="0"
                          y1={MID - MID * f}
                          x2={W}
                          y2={MID - MID * f}
                          stroke="rgb(var(--c-line) / 0.08)"
                          strokeDasharray="3 6"
                        />
                        <line
                          x1="0"
                          y1={MID + MID * f}
                          x2={W}
                          y2={MID + MID * f}
                          stroke="rgb(var(--c-line) / 0.08)"
                          strokeDasharray="3 6"
                        />
                      </g>
                    ))}

                    {view.rows.map((r, i) => {
                      const bw = W / view.rows.length
                      const x = i * bw
                      const dh = (Math.abs(r.d) / view.maxD) * (MID - 8)
                      const vh = (Math.abs(r.v) / view.maxV) * (MID - 8)
                      const opposing = r.d * r.v < 0
                      return (
                        <g key={r.gene}>
                          {/* disease, always upward from the axis */}
                          <rect
                            x={x}
                            y={MID - dh}
                            width={Math.max(0.6, bw - 0.55)}
                            height={dh}
                            fill={
                              r.d > 0 ? 'rgb(var(--c-ember) / 0.75)' : 'rgb(var(--c-signal) / 0.6)'
                            }
                          />
                          {/* compound, always downward */}
                          <rect
                            x={x}
                            y={MID}
                            width={Math.max(0.6, bw - 0.55)}
                            height={vh}
                            fill={
                              opposing ? 'rgb(var(--c-mint) / 0.8)' : 'rgb(var(--c-ember) / 0.5)'
                            }
                            style={{ transition: 'height 0.75s cubic-bezier(0.22,1,0.36,1), fill 0.5s' }}
                          />
                        </g>
                      )
                    })}

                    <text
                      x="8"
                      y="16"
                      className="fill-[rgb(var(--c-faint))] font-mono text-[9px] uppercase tracking-[0.2em]"
                    >
                      up in disease
                    </text>
                    <text
                      x="8"
                      y={H - 8}
                      className="fill-[rgb(var(--c-faint))] font-mono text-[9px] uppercase tracking-[0.2em]"
                    >
                      compound response
                    </text>
                  </svg>

                  <p className="mt-4 border-t border-line/10 pt-3.5 text-[12px] leading-relaxed text-dim">
                    {view.cosine < -0.5 ? (
                      <>
                        <span className="text-mint">Strong mirror.</span> The compound&rsquo;s
                        response is close to the inverse of the disease profile across the whole
                        gene set.
                      </>
                    ) : view.cosine > 0.5 ? (
                      <>
                        <span className="text-ember">Reinforcing.</span> This compound pushes
                        expression the same way the disease does — included here as a negative
                        control, not as a candidate.
                      </>
                    ) : (
                      <>
                        <span className="text-dim">Weak alignment.</span> No consistent
                        relationship between this compound&rsquo;s response and the disease
                        profile.
                      </>
                    )}
                  </p>
                </GlassPanel>
              </Reveal>

              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-1 xl:content-start">
                <Reveal>
                  <CosineDial value={view.cosine} />
                </Reveal>
                <Reveal delay={0.06}>
                  <GlassPanel kind="metric" className="p-4">
                    <Hud className="mb-3 block">Genes opposed</Hud>
                    <div className="font-display text-[26px] font-semibold leading-none text-mint">
                      <AnimatedNumber value={view.reversedCount} />
                      <span className="text-[15px] text-faint">/{view.rows.length}</span>
                    </div>
                    <p className="mt-2 text-[11px] leading-snug text-faint">
                      genes where compound and disease point in opposite directions
                    </p>
                  </GlassPanel>
                </Reveal>
                <Reveal delay={0.12}>
                  <GlassPanel kind="evidence" className="p-4">
                    <Provenance kind="computed" className="mb-2.5" />
                    <p className="text-[11.5px] leading-relaxed text-dim">
                      Cosine treats every gene as equally informative and ignores rank. The
                      repository also implements WTCS, a Connectivity-Map-style rank-based score,
                      available as an alternative method.
                    </p>
                  </GlassPanel>
                </Reveal>
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  )
}

/** A gauge that runs -1 to +1 with reversal on the left. */
function CosineDial({ value }: { value: number }) {
  const R = 62
  const CIRC = Math.PI * R // half circle
  // map -1..1 to 0..1 along the arc
  const t = (value + 1) / 2
  const good = value < 0

  return (
    <GlassPanel kind="metric" className="p-4">
      <Hud className="mb-1 block">Cosine similarity</Hud>
      <div className="relative flex justify-center pt-2">
        <svg width="164" height="98" viewBox="0 0 164 98" aria-hidden>
          <path
            d={`M 20 84 A ${R} ${R} 0 0 1 144 84`}
            fill="none"
            stroke="rgb(var(--c-line) / 0.14)"
            strokeWidth="9"
            strokeLinecap="round"
          />
          <path
            d={`M 20 84 A ${R} ${R} 0 0 1 144 84`}
            fill="none"
            stroke={good ? 'rgb(var(--c-mint))' : 'rgb(var(--c-ember))'}
            strokeWidth="9"
            strokeLinecap="round"
            strokeDasharray={CIRC}
            strokeDashoffset={CIRC * (1 - t)}
            style={{ transition: 'stroke-dashoffset 0.9s cubic-bezier(0.22,1,0.36,1), stroke 0.5s' }}
          />
          {/* midpoint tick: zero correlation */}
          <line x1="82" y1="14" x2="82" y2="24" stroke="rgb(var(--c-line) / 0.4)" strokeWidth="1.5" />
        </svg>
        <div className="absolute inset-x-0 bottom-1 text-center">
          <div
            className={cx(
              'num text-[27px] font-semibold leading-none',
              good ? 'text-mint' : 'text-ember',
            )}
          >
            {value.toFixed(3)}
          </div>
        </div>
      </div>
      <div className="mt-1 flex justify-between">
        <Hud className="text-mint">−1 reversal</Hud>
        <Hud className="text-ember">+1 same</Hud>
      </div>
    </GlassPanel>
  )
}
