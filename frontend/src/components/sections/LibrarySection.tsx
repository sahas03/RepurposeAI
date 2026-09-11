import { AnimatePresence, motion } from 'framer-motion'
import { GlassPanel, SectionHead } from '@/components/ui/GlassPanel'
import { Hud, Metric, Provenance } from '@/components/ui/Hud'
import { Reveal } from '@/components/ui/Reveal'
import { DrugConstellation, useConstellation } from '@/components/viz/DrugConstellation'
import { useApp } from '@/store/useApp'
import { EmptyField } from './SignatureSection'

/**
 * Stage 02 and 03 shown as one moment, because they are one moment: the
 * library exists, and then scoring rearranges it. The constellation is the
 * same component before and after; only the data driving the radius changes.
 */
export function LibrarySection() {
  const dataset = useApp((s) => s.dataset)
  const result = useApp((s) => s.result)
  const openDetail = useApp((s) => s.openDetail)
  const selected = useApp((s) => s.selected)
  const nodes = useConstellation(dataset, result)
  const scored = !!result

  return (
    <section id="library" className="relative px-5 py-28 sm:px-8">
      <div className="mx-auto w-full max-w-[1400px]">
        <Reveal>
          <SectionHead
            index="03"
            eyebrow="Stage 02 + 03 output"
            title="Then the library reorganises itself."
            lede="Each point is one compound. Before scoring, its distance from the centre is the size of its own transcriptional effect. After scoring, distance becomes reversal rank — and the compounds that mirror the disease are pulled inward."
          />
        </Reveal>

        {!dataset ? (
          <EmptyField label="Loading the compound library" />
        ) : (
          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_320px]">
            <Reveal>
              <GlassPanel kind="primary" ticks className="p-4 sm:p-6">
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                  <Hud>
                    {scored ? 'Arranged by reversal rank' : 'Arranged by signature magnitude'}
                  </Hud>
                  <div className="flex flex-wrap items-center gap-3">
                    <LegendDot color="bg-dim" label="Library" />
                    <LegendDot color="bg-mint" label="Shortlisted" />
                    <LegendDot color="bg-iris" label="Known reference" />
                  </div>
                </div>
                <DrugConstellation
                  nodes={nodes}
                  scored={scored}
                  selected={selected}
                  onSelect={openDetail}
                  className="mx-auto max-w-[620px]"
                />
              </GlassPanel>
            </Reveal>

            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-1 lg:content-start">
              <Reveal delay={0.05}>
                <Metric
                  label="Compounds in library"
                  value={dataset.drugs.length}
                  accent="signal"
                  note={`profiled across ${dataset.genes.length} shared genes`}
                />
              </Reveal>
              <Reveal delay={0.1}>
                <Metric
                  label="Compounds scored"
                  value={result?.drugsScored ?? 0}
                  accent="mint"
                  text={result ? undefined : '—'}
                  note={result ? result.methodLabel : 'awaiting a run'}
                />
              </Reveal>
              <Reveal delay={0.15}>
                <Metric
                  label="Shortlist size"
                  value={result?.candidates.length ?? 0}
                  accent="iris"
                  text={result ? undefined : '—'}
                  note="carried into safety, novelty and validation"
                />
              </Reveal>

              <AnimatePresence>
                {result && (
                  <motion.div
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
                  >
                    <GlassPanel kind="data" className="p-4">
                      <Hud className="mb-2.5 block">Score range</Hud>
                      <div className="space-y-2">
                        <RangeRow
                          label="Strongest reversal"
                          value={result.allScores[0].reversalScore}
                          drug={result.allScores[0].drug}
                          accent="text-mint"
                        />
                        <RangeRow
                          label="Strongest reinforcement"
                          value={result.allScores[result.allScores.length - 1].reversalScore}
                          drug={result.allScores[result.allScores.length - 1].drug}
                          accent="text-ember"
                        />
                      </div>
                      <p className="mt-3 border-t border-line/10 pt-2.5 text-[11px] leading-relaxed text-faint">
                        A negative score means the compound pushes expression opposite to the
                        disease. A positive score means it pushes the same way — the wrong
                        direction, and useful as a negative control.
                      </p>
                    </GlassPanel>
                  </motion.div>
                )}
              </AnimatePresence>

              <Reveal delay={0.2}>
                <GlassPanel kind="evidence" className="p-4">
                  <Provenance kind="synthetic" className="mb-2.5" />
                  <p className="text-[11.5px] leading-relaxed text-dim">
                    Compound identifiers here are placeholders from the generated benchmark. Three
                    of them carry a deliberately planted reversal signal, which is what makes the
                    validation check at the end of this page meaningful.
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

function LegendDot({ color, label }: { color: string; label: string }) {
  return (
    <span className="flex items-center gap-1.5">
      <span className={`h-2 w-2 rounded-full ${color}`} />
      <Hud>{label}</Hud>
    </span>
  )
}

function RangeRow({
  label,
  value,
  drug,
  accent,
}: {
  label: string
  value: number
  drug: string
  accent: string
}) {
  return (
    <div>
      <div className="flex items-baseline justify-between gap-3">
        <Hud>{label}</Hud>
        <span className={`num text-[12px] ${accent}`}>{value.toFixed(4)}</span>
      </div>
      <div className="truncate font-mono text-[10.5px] text-faint">{drug}</div>
    </div>
  )
}
