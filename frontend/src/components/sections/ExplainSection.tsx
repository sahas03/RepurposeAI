import { motion } from 'framer-motion'
import { useMemo, useState } from 'react'
import { cx } from '@/lib/cx'
import { GlassPanel, SectionHead } from '@/components/ui/GlassPanel'
import { Hud, Provenance } from '@/components/ui/Hud'
import { Reveal } from '@/components/ui/Reveal'
import { useExplain } from '@/api/useExplain'
import { useApp, useSelectedCandidate } from '@/store/useApp'
import { EmptyField } from './SignatureSection'

/**
 * "Why this drug?" as an explorable graph rather than a paragraph.
 *
 * The cosine score is a sum of per-gene products, which means the explanation
 * is not an approximation of the model - it *is* the model, decomposed. Each
 * edge here carries a real term of that sum, its thickness is that term's
 * magnitude, and clicking a gene shows the arithmetic.
 */

const W = 940
const NODE_X = { disease: 96, gene: 470, drug: 848 }

export function ExplainSection() {
  const dataset = useApp((s) => s.dataset)
  const result = useApp((s) => s.result)
  const focusGene = useApp((s) => s.focusGene)
  const setFocusGene = useApp((s) => s.setFocusGene)
  const selected = useSelectedCandidate()
  const candidate = selected ?? result?.candidates[0] ?? null
  const [topN] = useState(10)

  // Gene contributions come from the backend (GET /api/candidates/{drug}/explain),
  // which decomposes the score using the same Python that produced it.
  const {
    genes,
    loading: genesLoading,
    error: genesError,
  } = useExplain(result ? result.dataset.id : null, candidate?.drug ?? null, topN)

  /** Share of the cosine numerator explained by these genes. */
  const share = useMemo(() => {
    if (!dataset || !result || !candidate || genes.length === 0) return null
    const j = dataset.drugs.indexOf(candidate.drug)
    const nd = dataset.drugs.length
    let totalAbs = 0
    for (let i = 0; i < dataset.genes.length; i++) {
      totalAbs += Math.abs(result.diseaseVec[i] * dataset.matrix[i * nd + j])
    }
    const shown = genes.reduce((s, g) => s + Math.abs(g.contribution), 0)
    const reversed = genes.filter((g) => g.direction === 'reversed by drug').length
    return { pct: totalAbs ? (shown / totalAbs) * 100 : 0, reversed }
  }, [dataset, result, candidate, genes])

  const H = 96 + topN * 42
  const maxAbs = Math.max(...genes.map((g) => Math.abs(g.contribution)), 1e-9)
  const active = genes.find((g) => g.gene === focusGene) ?? null

  return (
    <section id="explain" className="relative px-5 py-28 sm:px-8">
      <div className="mx-auto w-full max-w-[1400px]">
        <Reveal>
          <SectionHead
            index="07"
            eyebrow="Stage 05 output"
            title="Why this drug?"
            lede="Not a black box explaining itself after the fact. The cosine score is the sum of one product per gene, so pulling it apart gene by gene reproduces the score exactly. Follow any edge to see the arithmetic behind it."
          />
        </Reveal>

        {!candidate ? (
          <EmptyField label="No candidate selected" />
        ) : genesError ? (
          <EmptyField label="Could not load the explanation" hint={genesError} />
        ) : genes.length === 0 ? (
          <EmptyField
            label={genesLoading ? 'Decomposing the score…' : 'No contributions to show'}
            hint={
              genesLoading
                ? 'Asking the pipeline which genes produced this score.'
                : undefined
            }
          />
        ) : (
          <div className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_330px]">
            <Reveal>
              <GlassPanel kind="primary" ticks className="overflow-x-auto p-4 sm:p-6">
                <div className="min-w-[720px]">
                  <svg
                    viewBox={`0 0 ${W} ${H}`}
                    className="w-full"
                    role="img"
                    aria-label={`Reasoning graph for ${candidate.drug}`}
                    onMouseLeave={() => setFocusGene(null)}
                  >
                    {/* edges */}
                    {genes.map((g, i) => {
                      const y = 62 + i * 42
                      const reversed = g.direction === 'reversed by drug'
                      const w = 0.8 + (Math.abs(g.contribution) / maxAbs) * 4.2
                      const dim = active && active.gene !== g.gene
                      const stroke = reversed ? 'var(--c-mint)' : 'var(--c-ember)'
                      const op = dim ? 0.12 : active ? 0.95 : 0.42
                      // One continuous path disease -> gene -> compound, so the
                      // travelling pulse can ride the whole route without a jump.
                      const d =
                        curve(NODE_X.disease + 44, H / 2, NODE_X.gene - 54, y) +
                        ' ' +
                        curve(NODE_X.gene + 54, y, NODE_X.drug - 44, H / 2).replace(/^M[^C]*/, 'L ' + (NODE_X.gene + 54) + ' ' + y + ' ')
                      return (
                        <g key={`e-${g.gene}`} style={{ transition: 'opacity 0.3s' }}>
                          <path d={d} fill="none" stroke={`rgb(${stroke} / ${op})`} strokeWidth={w} />
                          {/* a pulse riding the edge, so the graph reads as live */}
                          {!dim && (
                            <circle r={2.4} fill={`rgb(${stroke})`} opacity={0.9}>
                              <animateMotion
                                dur={`${2.6 + (i % 4) * 0.5}s`}
                                repeatCount="indefinite"
                                path={d}
                              />
                            </circle>
                          )}
                        </g>
                      )
                    })}

                    {/* disease terminal */}
                    <Terminal
                      x={NODE_X.disease}
                      y={H / 2}
                      label="Disease"
                      sub="RA signature"
                      accent="ember"
                    />
                    {/* drug terminal */}
                    <Terminal
                      x={NODE_X.drug}
                      y={H / 2}
                      label="Compound"
                      sub={candidate.drug}
                      accent="mint"
                    />

                    {/* gene nodes */}
                    {genes.map((g, i) => {
                      const y = 62 + i * 42
                      const reversed = g.direction === 'reversed by drug'
                      const on = active?.gene === g.gene
                      return (
                        <g
                          key={g.gene}
                          className="cursor-pointer"
                          data-cursor="node"
                          onMouseEnter={() => setFocusGene(g.gene)}
                          onClick={() => setFocusGene(g.gene)}
                        >
                          <rect
                            x={NODE_X.gene - 54}
                            y={y - 14}
                            width={108}
                            height={28}
                            rx={5}
                            fill={on ? 'rgb(var(--c-raised))' : 'rgb(var(--glass) / 0.7)'}
                            stroke={
                              on
                                ? reversed
                                  ? 'rgb(var(--c-mint))'
                                  : 'rgb(var(--c-ember))'
                                : 'rgb(var(--c-line) / 0.2)'
                            }
                            strokeWidth={on ? 1.4 : 1}
                            style={{ transition: 'all 0.25s' }}
                          />
                          <text
                            x={NODE_X.gene}
                            y={y + 4}
                            textAnchor="middle"
                            className="pointer-events-none fill-[rgb(var(--c-ink))] font-mono text-[11px]"
                          >
                            {g.gene}
                          </text>
                          <circle
                            cx={NODE_X.gene - 62}
                            cy={y}
                            r={3}
                            fill={reversed ? 'rgb(var(--c-mint))' : 'rgb(var(--c-ember))'}
                          />
                        </g>
                      )
                    })}

                    <text
                      x={NODE_X.gene}
                      y={26}
                      textAnchor="middle"
                      className="fill-[rgb(var(--c-faint))] font-mono text-[9px] uppercase tracking-[0.22em]"
                    >
                      top {topN} contributing genes
                    </text>
                  </svg>
                </div>

                <div className="mt-4 flex flex-wrap items-center gap-4 border-t border-line/10 pt-3.5">
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-mint" />
                    <Hud>Reversed by compound</Hud>
                  </span>
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-ember" />
                    <Hud>Reinforced (unwanted)</Hud>
                  </span>
                  <Hud className="ml-auto text-faint">Edge width = contribution magnitude</Hud>
                </div>
              </GlassPanel>
            </Reveal>

            <div className="space-y-4">
              <Reveal>
                <GlassPanel kind="data" className="p-5">
                  <Hud className="mb-3 block">Summary</Hud>
                  <p className="text-[13.5px] leading-relaxed text-ink text-pretty">
                    <span className="font-mono text-mint">{candidate.drug}</span> reverses{' '}
                    <span className="num text-mint">{share?.reversed ?? 0}</span> of the top{' '}
                    <span className="num">{topN}</span> genes driving its score, including{' '}
                    <span className="font-mono text-ink">
                      {genes
                        .slice(0, 3)
                        .map((g) => g.gene)
                        .join(', ')}
                    </span>
                    .
                  </p>
                  {share && (
                    <p className="mt-3 text-[11.5px] leading-relaxed text-faint">
                      These {topN} genes account for{' '}
                      <span className="num text-dim">{share.pct.toFixed(1)}%</span> of the total
                      absolute contribution across all {result?.genesMatched} genes.
                    </p>
                  )}
                </GlassPanel>
              </Reveal>

              <Reveal delay={0.06}>
                <GlassPanel kind="secondary" className="min-h-[190px] p-5">
                  <Hud className="mb-3 block">
                    {active ? `Gene · ${active.gene}` : 'Select a gene'}
                  </Hud>
                  {active ? (
                    <motion.dl
                      key={active.gene}
                      initial={{ opacity: 0, y: 6 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ duration: 0.3 }}
                      className="space-y-2.5"
                    >
                      <Row k="Disease z-score" v={active.diseaseLogFC.toFixed(4)} accent="ember" />
                      <Row
                        k="Compound z-score"
                        v={active.drugZscore.toFixed(4)}
                        accent={active.drugZscore * active.diseaseLogFC < 0 ? 'mint' : 'ember'}
                      />
                      <div className="border-t border-line/10 pt-2.5">
                        <Row
                          k="Product"
                          v={active.contribution.toFixed(4)}
                          accent={active.contribution < 0 ? 'mint' : 'ember'}
                          bold
                        />
                      </div>
                      <p className="pt-1 text-[11.5px] leading-relaxed text-dim">
                        {active.contribution < 0
                          ? 'The two point in opposite directions, so this gene pushes the cosine score negative — toward reversal.'
                          : 'Both point the same way, so this gene pushes the score positive and works against the reversal signal.'}
                      </p>
                    </motion.dl>
                  ) : (
                    <p className="text-[12px] leading-relaxed text-faint">
                      Hover or click any gene in the graph to see the two z-scores and the product
                      they contribute to the cosine sum.
                    </p>
                  )}
                </GlassPanel>
              </Reveal>

              <Reveal delay={0.12}>
                <GlassPanel kind="warning" className="p-5">
                  <Hud className="mb-2.5 block text-amber">Pathway enrichment unavailable</Hud>
                  <p className="text-[11.5px] leading-relaxed text-ink text-pretty">
                    The Python pipeline runs pathway enrichment through the Enrichr API. It is not
                    run here for two reasons: it needs live network access, and the identifiers in
                    this benchmark are placeholders that no pathway database contains. On a real
                    RA signature with HGNC symbols, this panel would list enriched KEGG terms for
                    the reversed genes above.
                  </p>
                  <Provenance kind="standby" className="mt-3" />
                </GlassPanel>
              </Reveal>
            </div>
          </div>
        )}
      </div>
    </section>
  )
}

function Row({
  k,
  v,
  accent,
  bold,
}: {
  k: string
  v: string
  accent?: 'mint' | 'ember'
  bold?: boolean
}) {
  return (
    <div className="flex items-baseline justify-between gap-3">
      <Hud>{k}</Hud>
      <span
        className={cx(
          'num',
          bold ? 'text-[15px] font-semibold' : 'text-[12.5px]',
          accent === 'mint' ? 'text-mint' : accent === 'ember' ? 'text-ember' : 'text-ink',
        )}
      >
        {v}
      </span>
    </div>
  )
}

function Terminal({
  x,
  y,
  label,
  sub,
  accent,
}: {
  x: number
  y: number
  label: string
  sub: string
  accent: 'mint' | 'ember'
}) {
  const color = accent === 'mint' ? 'var(--c-mint)' : 'var(--c-ember)'
  return (
    <g>
      <circle cx={x} cy={y} r={44} fill={`rgb(${color} / 0.07)`} stroke={`rgb(${color} / 0.4)`} />
      <circle
        cx={x}
        cy={y}
        r={52}
        fill="none"
        stroke={`rgb(${color} / 0.15)`}
        strokeDasharray="3 5"
      />
      <text
        x={x}
        y={y - 5}
        textAnchor="middle"
        className="fill-[rgb(var(--c-faint))] font-mono text-[8px] uppercase tracking-[0.2em]"
      >
        {label}
      </text>
      <text
        x={x}
        y={y + 11}
        textAnchor="middle"
        className="fill-[rgb(var(--c-ink))] font-mono text-[10px]"
      >
        {sub.length > 13 ? sub.slice(0, 12) + '…' : sub}
      </text>
    </g>
  )
}

/** A flat-ish cubic between two points, biased horizontally. */
function curve(x1: number, y1: number, x2: number, y2: number) {
  const dx = (x2 - x1) * 0.55
  return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`
}
