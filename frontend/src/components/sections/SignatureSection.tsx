import { motion, useReducedMotion } from 'framer-motion'
import { useMemo, useState } from 'react'
import { cx } from '@/lib/cx'
import type { DiseaseGene } from '@/engine/types'
import { GlassPanel, SectionHead } from '@/components/ui/GlassPanel'
import { Hud, Metric, Provenance } from '@/components/ui/Hud'
import { Reveal } from '@/components/ui/Reveal'
import { useApp } from '@/store/useApp'

/**
 * The disease signature, shown as the thing it actually is: a field of genes
 * with a direction and a magnitude.
 *
 * Cells are ordered by logFC so the whole field reads as a single gradient
 * from most up-regulated to most down-regulated. The two poles use the app's
 * colour language - ember for up in disease, signal-blue for down - and mint
 * is deliberately absent here, because mint means correction, and nothing has
 * corrected anything yet.
 */
export function SignatureSection() {
  const dataset = useApp((s) => s.dataset)
  const [hover, setHover] = useState<DiseaseGene | null>(null)
  const reduced = useReducedMotion()

  const stats = useMemo(() => {
    if (!dataset) return null
    const genes = [...dataset.disease].sort((a, b) => b.logFC - a.logFC)
    const up = genes.filter((g) => g.logFC > 0)
    const down = genes.filter((g) => g.logFC <= 0)
    const maxAbs = Math.max(...genes.map((g) => Math.abs(g.logFC)))
    // Euclidean norm of the logFC vector: how loud the signature is overall.
    const strength = Math.sqrt(genes.reduce((s, g) => s + g.logFC ** 2, 0))
    const significant = genes.filter((g) => g.pvalue < 0.01).length
    return { genes, up, down, maxAbs, strength, significant }
  }, [dataset])

  return (
    <section id="signature" className="relative px-5 py-28 sm:px-8">
      <div className="mx-auto w-full max-w-[1400px]">
        <Reveal>
          <SectionHead
            index="02"
            eyebrow="Stage 01 output"
            title="Every disease writes something down."
            lede="Rheumatoid arthritis leaves a measurable fingerprint in gene expression: hundreds of genes pushed up, hundreds pushed down. That vector is the entire input to everything that follows."
          />
        </Reveal>

        {!stats ? (
          <EmptyField label="Parsing the disease signature" />
        ) : (
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
            <Reveal>
              <GlassPanel kind="primary" ticks className="overflow-hidden p-5 sm:p-7">
                <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <Hud className="mb-1.5 block">Differential expression field</Hud>
                    <p className="text-[12px] text-dim">
                      {stats.genes.length} genes, ordered by log fold change
                    </p>
                  </div>
                  <Legend />
                </div>

                {/* The field itself. Fixed-count grid so it stays a rectangle. */}
                <div
                  className="grid gap-[3px]"
                  style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(16px, 1fr))' }}
                  onMouseLeave={() => setHover(null)}
                >
                  {stats.genes.map((g, i) => {
                    const t = Math.abs(g.logFC) / stats.maxAbs
                    const up = g.logFC > 0
                    return (
                      <motion.button
                        key={g.gene}
                        data-cursor="node"
                        onMouseEnter={() => setHover(g)}
                        onFocus={() => setHover(g)}
                        aria-label={`${g.gene}, log fold change ${g.logFC.toFixed(2)}`}
                        className="aspect-square rounded-[2px] outline-none ring-offset-2 transition-transform duration-200 hover:scale-[1.45] hover:ring-1 hover:ring-ink/40 focus-visible:scale-[1.45]"
                        style={{
                          background: up
                            ? `rgb(var(--c-ember) / ${0.14 + t * 0.86})`
                            : `rgb(var(--c-signal) / ${0.14 + t * 0.86})`,
                        }}
                        initial={reduced ? false : { opacity: 0, scale: 0.4 }}
                        whileInView={{ opacity: 1, scale: 1 }}
                        viewport={{ once: true }}
                        transition={{
                          duration: 0.45,
                          // Sweep left-to-right rather than all at once.
                          delay: Math.min(0.9, (i / stats.genes.length) * 1.1),
                          ease: [0.22, 1, 0.36, 1],
                        }}
                      />
                    )
                  })}
                </div>

                {/* Readout rail: always occupies space so the grid never jumps. */}
                <div className="mt-5 flex min-h-[46px] items-center border-t border-line/10 pt-4">
                  {hover ? (
                    <div className="flex flex-wrap items-center gap-x-7 gap-y-1.5">
                      <span className="font-mono text-[14px] font-medium text-ink">
                        {hover.gene}
                      </span>
                      <Readout
                        k="logFC"
                        v={hover.logFC.toFixed(3)}
                        accent={hover.logFC > 0 ? 'ember' : 'signal'}
                      />
                      <Readout k="p-value" v={hover.pvalue.toExponential(2)} />
                      <Readout
                        k="direction"
                        v={hover.logFC > 0 ? 'up in disease' : 'down in disease'}
                        accent={hover.logFC > 0 ? 'ember' : 'signal'}
                      />
                    </div>
                  ) : (
                    <p className="text-[12px] text-faint">
                      Hover any cell to inspect that gene&rsquo;s fold change and significance.
                    </p>
                  )}
                </div>
              </GlassPanel>
            </Reveal>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1 lg:content-start">
              <Reveal delay={0.05}>
                <Metric label="Genes up in disease" value={stats.up.length} accent="ember" />
              </Reveal>
              <Reveal delay={0.1}>
                <Metric label="Genes down in disease" value={stats.down.length} accent="signal" />
              </Reveal>
              <Reveal delay={0.15}>
                <Metric
                  label="Signature strength"
                  value={stats.strength}
                  decimals={1}
                  accent="iris"
                  note="Euclidean norm of the logFC vector"
                />
              </Reveal>
              <Reveal delay={0.2}>
                <Metric
                  label="p < 0.01"
                  value={stats.significant}
                  accent="mint"
                  note={`of ${stats.genes.length} genes tested`}
                />
              </Reveal>
              <Reveal delay={0.25}>
                <GlassPanel kind="evidence" className="p-4">
                  <Provenance kind="synthetic" className="mb-2.5" />
                  <p className="text-[11.5px] leading-relaxed text-dim">
                    These fold changes come from the repository&rsquo;s generated benchmark, not
                    from a GEO series. The pipeline reads a real RA signature in exactly the same
                    three columns — gene, logFC, pvalue — with no code change.
                  </p>
                </GlassPanel>
              </Reveal>
            </div>
          </div>
        )}
      </div>
    </section>
  )
}

function Readout({ k, v, accent }: { k: string; v: string; accent?: 'ember' | 'signal' }) {
  return (
    <span className="flex items-baseline gap-2">
      <Hud>{k}</Hud>
      <span
        className={cx(
          'num text-[12.5px]',
          accent === 'ember' ? 'text-ember' : accent === 'signal' ? 'text-signal' : 'text-ink',
        )}
      >
        {v}
      </span>
    </span>
  )
}

function Legend() {
  return (
    <div className="flex items-center gap-3">
      <span className="flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-[2px] bg-ember" />
        <Hud>Up</Hud>
      </span>
      <span className="h-3 w-px bg-line/20" />
      <span className="flex items-center gap-1.5">
        <span className="h-2.5 w-2.5 rounded-[2px] bg-signal" />
        <Hud>Down</Hud>
      </span>
    </div>
  )
}

/**
 * The shared empty state. It is not a spinner: a slowly rotating molecular
 * ring, the same one used everywhere data has not arrived, so an empty
 * section still belongs to the product.
 */
export function EmptyField({ label, hint }: { label: string; hint?: string }) {
  return (
    <GlassPanel kind="secondary" className="flex flex-col items-center justify-center px-6 py-20">
      <svg width="76" height="76" viewBox="0 0 76 76" className="animate-slow-spin" aria-hidden>
        <circle cx="38" cy="38" r="30" stroke="rgb(var(--c-line) / 0.18)" fill="none" />
        <circle cx="38" cy="38" r="20" stroke="rgb(var(--c-line) / 0.12)" fill="none" />
        {Array.from({ length: 6 }, (_, i) => {
          const a = (i / 6) * Math.PI * 2
          return (
            <circle
              key={i}
              cx={38 + Math.cos(a) * 30}
              cy={38 + Math.sin(a) * 30}
              r="3.2"
              fill="rgb(var(--c-mint))"
              opacity={0.25 + (i % 3) * 0.22}
            />
          )
        })}
        <circle cx="38" cy="38" r="4" fill="rgb(var(--c-mint))" opacity="0.5" />
      </svg>
      <p className="mt-6 font-display text-[15px] font-medium text-ink">{label}</p>
      <p className="mt-2 max-w-sm text-center text-[12px] leading-relaxed text-faint">
        {hint ?? 'Run the pipeline from the hero, or the button in the navigation, to populate this view with live output.'}
      </p>
    </GlassPanel>
  )
}
