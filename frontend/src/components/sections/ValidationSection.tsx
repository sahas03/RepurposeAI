import { motion, useInView } from 'framer-motion'
import { useMemo, useRef } from 'react'
import { cx } from '@/lib/cx'
import { DRUG_CLASSES, KNOWN_VALIDATION_SETS, formatValidationStatement } from '@/engine/validate'
import { GlassPanel, SectionHead } from '@/components/ui/GlassPanel'
import { AnimatedNumber, Hud, Metric, Provenance } from '@/components/ui/Hud'
import { Reveal } from '@/components/ui/Reveal'
import { useApp } from '@/store/useApp'
import { EmptyField } from './SignatureSection'

/**
 * The verification chamber.
 *
 * This is the section that has to be the most honest one on the page, because
 * it is the one most easily misread. Two distinct checks exist and they are
 * never merged: recovery of real known drugs (which needs real compound
 * names), and the planted-signal check on the synthetic benchmark. Whichever
 * one is running is stated plainly, and the word "clinical" appears only to
 * say that this is not it.
 */
export function ValidationSection() {
  const result = useApp((s) => s.result)
  const settings = useApp((s) => s.settings)
  const ref = useRef<HTMLDivElement>(null)
  const inView = useInView(ref, { once: true, margin: '-20%' })

  const reference = KNOWN_VALIDATION_SETS[settings.diseaseName.toLowerCase()] ?? []

  /** Where the planted reinforcing controls landed in the *full* ordering. */
  const controls = useMemo(() => {
    if (!result?.synthetic) return []
    return result.synthetic.reinforcingPlanted.map((drug) => {
      const i = result.allScores.findIndex((s) => s.drug === drug)
      return { drug, rank: i + 1, total: result.allScores.length, score: result.allScores[i]?.reversalScore ?? 0 }
    })
  }, [result])

  const passed = result?.synthetic
    ? result.synthetic.recoveredCount === result.synthetic.plantedTotal
    : (result?.recovery?.recoveredCount ?? 0) > 0

  return (
    <section id="validation" className="relative px-5 py-28 sm:px-8" ref={ref}>
      <div className="mx-auto w-full max-w-[1400px]">
        <Reveal>
          <SectionHead
            index="08"
            eyebrow="Stage 06 output"
            title="Does the method actually work?"
            lede="A ranking is worthless unless it can re-find something already known to be true. This is the check that makes everything above it credible — and the one place where being precise about what was tested matters more than the result."
          />
        </Reveal>

        {!result ? (
          <EmptyField label="Validation has not run" />
        ) : (
          <div className="space-y-5">
            {/* --- the verdict ------------------------------------------- */}
            <Reveal>
              <GlassPanel
                kind="primary"
                ticks
                className="relative overflow-hidden p-6 sm:p-10"
              >
                <div className="grid items-center gap-8 lg:grid-cols-[auto_minmax(0,1fr)]">
                  <Seal passed={passed} active={inView} />

                  <div className="min-w-0">
                    <div className="mb-3 flex flex-wrap items-center gap-2.5">
                      <Provenance kind={result.synthetic ? 'synthetic' : 'real'} />
                      <span className="rounded-full border border-line/18 px-2.5 py-1 font-mono text-[9px] uppercase tracking-hud text-dim">
                        {result.synthetic
                          ? 'Ground-truth sanity check'
                          : 'Known-drug recovery'}
                      </span>
                    </div>

                    <h3 className="font-display text-[26px] font-semibold leading-tight tracking-[-0.03em] sm:text-[32px]">
                      {result.synthetic
                        ? passed
                          ? 'Every planted signal was recovered.'
                          : 'Planted signals were only partly recovered.'
                        : passed
                          ? 'Known treatments were re-discovered blind.'
                          : 'No known treatments were recovered.'}
                    </h3>

                    <p className="mt-4 max-w-2xl text-[13.5px] leading-relaxed text-dim text-pretty">
                      {result.synthetic ? (
                        <>
                          The benchmark contains {result.synthetic.plantedTotal} compounds built to
                          mirror the disease signature and{' '}
                          {result.synthetic.reinforcingPlanted.length} built to reinforce it. The
                          pipeline was not told which is which. It placed{' '}
                          <span className="num text-mint">
                            {result.synthetic.recoveredCount}/{result.synthetic.plantedTotal}
                          </span>{' '}
                          of the mirroring compounds in the top {settings.validationTopK}, and the
                          reinforcing ones at the bottom of the library.
                        </>
                      ) : (
                        formatValidationStatement(result.recovery!)
                      )}
                    </p>
                  </div>
                </div>
              </GlassPanel>
            </Reveal>

            {/* --- the numbers -------------------------------------------- */}
            {result.synthetic && (
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <Reveal delay={0.05}>
                  <Metric
                    label="Planted signals recovered"
                    text={`${result.synthetic.recoveredCount}/${result.synthetic.plantedTotal}`}
                    accent="mint"
                    note={`within the top ${settings.validationTopK}`}
                  />
                </Reveal>
                <Reveal delay={0.1}>
                  <Metric
                    label="Recovery rate"
                    value={result.synthetic.recoveryRate * 100}
                    suffix="%"
                    accent="mint"
                    note="synthetic ground truth only"
                  />
                </Reveal>
                <Reveal delay={0.15}>
                  <Metric
                    label="Negative controls"
                    value={controls.length}
                    accent="ember"
                    note="reinforcing compounds, expected to rank last"
                  />
                </Reveal>
                <Reveal delay={0.2}>
                  <Metric
                    label="Library searched"
                    value={result.drugsScored}
                    accent="signal"
                    note="compounds, ranked blind"
                  />
                </Reveal>
              </div>
            )}

            <div className="grid gap-5 lg:grid-cols-2">
              {/* --- recovered signals ---------------------------------- */}
              <Reveal>
                <GlassPanel kind="data" className="h-full p-5">
                  <Hud className="mb-4 block text-mint">Recovered</Hud>
                  <ul className="space-y-2.5">
                    {(result.synthetic?.recovered ?? result.recovery?.recoveredDrugs ?? []).map(
                      (drug, i) => {
                        const cand = result.candidates.find((c) => c.drug === drug)
                        return (
                          <motion.li
                            key={drug}
                            initial={{ opacity: 0, x: -12 }}
                            whileInView={{ opacity: 1, x: 0 }}
                            viewport={{ once: true }}
                            transition={{ duration: 0.5, delay: 0.1 + i * 0.12 }}
                            className="flex items-center justify-between gap-3 rounded-lg border border-mint/25 bg-mint/[0.05] px-3.5 py-2.5"
                          >
                            <span className="flex min-w-0 items-center gap-2.5">
                              <span className="text-[12px] text-mint">✓</span>
                              <span className="truncate font-mono text-[12.5px] text-ink">
                                {drug}
                              </span>
                              {DRUG_CLASSES[drug] && (
                                <span className="shrink-0 text-[10px] text-faint">
                                  {DRUG_CLASSES[drug]}
                                </span>
                              )}
                            </span>
                            {cand && (
                              <span className="num shrink-0 text-[11px] text-mint">
                                rank {cand.finalRank}
                              </span>
                            )}
                          </motion.li>
                        )
                      },
                    )}
                  </ul>

                  {controls.length > 0 && (
                    <>
                      <Hud className="mb-3 mt-6 block text-ember">
                        Negative controls, where they landed
                      </Hud>
                      <ul className="space-y-2">
                        {controls.map((c) => (
                          <li
                            key={c.drug}
                            className="flex items-center justify-between gap-3 rounded-lg border border-ember/25 px-3.5 py-2.5"
                          >
                            <span className="truncate font-mono text-[12px] text-dim">
                              {c.drug}
                            </span>
                            <span className="num shrink-0 text-[11px] text-ember">
                              {c.rank} / {c.total}
                            </span>
                          </li>
                        ))}
                      </ul>
                      <p className="mt-3 text-[11px] leading-relaxed text-faint">
                        Ranking these last is as important as ranking the others first — it shows
                        the score separates direction, not just magnitude.
                      </p>
                    </>
                  )}
                </GlassPanel>
              </Reveal>

              {/* --- what this is and is not ---------------------------- */}
              <Reveal delay={0.06}>
                <div className="grid h-full gap-5">
                  <GlassPanel kind="warning" className="p-5">
                    <Hud className="mb-2.5 block text-amber">What this result is not</Hud>
                    <p className="text-[12.5px] leading-relaxed text-ink text-pretty">
                      This is a computational sanity check on generated data. It demonstrates that
                      the ranking math separates a reversal signal from noise. It is not clinical
                      validation, not experimental evidence, and it says nothing about whether any
                      real compound treats rheumatoid arthritis.
                    </p>
                  </GlassPanel>

                  <GlassPanel kind="secondary" className="p-5">
                    <Hud className="mb-2.5 block">The real check, when real data lands</Hud>
                    <p className="mb-4 text-[12px] leading-relaxed text-dim">
                      With a genuine L1000 library, the same code checks whether these documented
                      rheumatoid arthritis treatments reappear in the top {settings.validationTopK}{' '}
                      without ever being told about them. Recovering them would be the strongest
                      evidence this method carries real signal.
                    </p>
                    <div className="flex flex-wrap gap-1.5">
                      {reference.map((d) => (
                        <span
                          key={d}
                          title={DRUG_CLASSES[d]}
                          className="rounded-md border border-iris/25 px-2.5 py-1 font-mono text-[10.5px] text-iris/90"
                        >
                          {d}
                        </span>
                      ))}
                    </div>
                    <p className="mt-4 border-t border-line/10 pt-3 text-[11px] leading-relaxed text-faint">
                      The current library contains none of these names, so the real check correctly
                      reports zero matches rather than inventing a result. That is the intended
                      behaviour, not a failure.
                    </p>
                  </GlassPanel>
                </div>
              </Reveal>
            </div>
          </div>
        )}
      </div>
    </section>
  )
}

/** The verification seal. It draws itself once, when it comes into view. */
function Seal({ passed, active }: { passed: boolean; active: boolean }) {
  const color = passed ? 'var(--c-mint)' : 'var(--c-amber)'
  return (
    <div className="relative mx-auto h-[168px] w-[168px] shrink-0">
      <svg viewBox="0 0 168 168" className="h-full w-full" aria-hidden>
        <circle
          cx="84"
          cy="84"
          r="78"
          fill="none"
          stroke={`rgb(${color} / 0.14)`}
          strokeDasharray="2 6"
          className="animate-slow-spin"
          style={{ transformOrigin: '84px 84px' }}
        />
        <motion.circle
          cx="84"
          cy="84"
          r="64"
          fill={`rgb(${color} / 0.05)`}
          stroke={`rgb(${color} / 0.55)`}
          strokeWidth="1.5"
          initial={{ pathLength: 0, opacity: 0 }}
          animate={active ? { pathLength: 1, opacity: 1 } : {}}
          transition={{ duration: 1.1, ease: [0.22, 1, 0.36, 1] }}
          style={{ rotate: -90, transformOrigin: '84px 84px' }}
        />
        <motion.path
          d="M60 86 L76 102 L110 66"
          fill="none"
          stroke={`rgb(${color})`}
          strokeWidth="4.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          initial={{ pathLength: 0 }}
          animate={active ? { pathLength: 1 } : {}}
          transition={{ duration: 0.65, delay: 0.75, ease: [0.22, 1, 0.36, 1] }}
        />
      </svg>
      <div className="absolute inset-x-0 -bottom-1 text-center">
        <span
          className={cx(
            'font-mono text-[10px] font-semibold uppercase tracking-hud',
            passed ? 'text-mint' : 'text-amber',
          )}
        >
          {passed ? 'Signal confirmed' : 'Partial signal'}
        </span>
      </div>
    </div>
  )
}

/** Exported for the footer summary strip. */
export function ValidationBadge() {
  const result = useApp((s) => s.result)
  if (!result?.synthetic) return null
  return (
    <span className="num text-mint">
      <AnimatedNumber value={result.synthetic.recoveryRate * 100} decimals={0} suffix="%" />
    </span>
  )
}
