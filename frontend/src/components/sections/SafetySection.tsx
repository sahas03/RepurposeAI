import { motion } from 'framer-motion'
import { cx } from '@/lib/cx'
import type { Candidate } from '@/engine/types'
import { GlassPanel, SectionHead } from '@/components/ui/GlassPanel'
import { Hud, Provenance, StatusDot } from '@/components/ui/Hud'
import { Reveal } from '@/components/ui/Reveal'
import { useApp, useSelectedCandidate } from '@/store/useApp'
import { EmptyField } from './SignatureSection'

/**
 * The screening stage, shown as a chamber a candidate passes through.
 *
 * The important design decision here is that inactive checks are displayed as
 * inactive rather than hidden or faked green. The Lipinski screen genuinely
 * cannot run without a structure descriptor table, and saying so is more
 * convincing than four invented ticks.
 */
export function SafetySection() {
  const result = useApp((s) => s.result)
  const selected = useSelectedCandidate()
  const candidate = selected ?? result?.candidates[0] ?? null

  return (
    <section id="safety" className="relative px-5 py-28 sm:px-8">
      <div className="mx-auto w-full max-w-[1400px]">
        <Reveal>
          <SectionHead
            index="05"
            eyebrow="Stage 04 output"
            title="A high score is not yet a candidate."
            lede="Reversal strength alone would rank a toxic compound above a safe one. This stage adds two more axes — a druglikeness proxy and a known-versus-novel label — and fuses all three into the final ranking with explicit weights."
          />
        </Reveal>

        {!result || !candidate ? (
          <EmptyField label="No candidates to screen yet" />
        ) : (
          <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <Reveal>
              <Chamber candidate={candidate} safetyActive={result.safetyActive} />
            </Reveal>

            <div className="space-y-5">
              <Reveal delay={0.06}>
                <ScoreFusion
                  candidate={candidate}
                  weights={result.settings.weights}
                  safetyActive={result.safetyActive}
                />
              </Reveal>
              <Reveal delay={0.12}>
                <GlassPanel kind="secondary" className="p-5">
                  <Hud className="mb-3 block">Shortlist composition</Hud>
                  <div className="flex gap-5">
                    <Tally
                      label="Novel candidates"
                      value={result.candidates.filter((c) => !c.knownForDisease).length}
                      accent="text-mint"
                    />
                    <Tally
                      label="Known references"
                      value={result.candidates.filter((c) => c.knownForDisease).length}
                      accent="text-iris"
                    />
                  </div>
                  <p className="mt-4 border-t border-line/10 pt-3 text-[11.5px] leading-relaxed text-faint">
                    Known hits are kept in the ranking, not filtered out. They are the evidence
                    that the method works, and discarding them would remove the only ground truth
                    the pipeline has.
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

function Chamber({ candidate, safetyActive }: { candidate: Candidate; safetyActive: boolean }) {
  const checks = [
    {
      name: 'Novelty label',
      active: true,
      state: candidate.knownForDisease ? 'KNOWN HIT' : 'NOVEL',
      accent: candidate.knownForDisease ? ('iris' as const) : ('mint' as const),
      note: candidate.knownForDisease
        ? 'documented for this disease in the reference set'
        : 'not present in the curated reference set for this disease',
    },
    {
      name: 'Molecular weight ≤ 500',
      active: safetyActive,
      state: safetyActive ? 'CHECKED' : 'STANDBY',
      accent: 'amber' as const,
      note: 'Lipinski rule 1',
    },
    {
      name: 'logP ≤ 5',
      active: safetyActive,
      state: safetyActive ? 'CHECKED' : 'STANDBY',
      accent: 'amber' as const,
      note: 'Lipinski rule 2',
    },
    {
      name: 'H-bond donors ≤ 5',
      active: safetyActive,
      state: safetyActive ? 'CHECKED' : 'STANDBY',
      accent: 'amber' as const,
      note: 'Lipinski rule 3',
    },
    {
      name: 'H-bond acceptors ≤ 10',
      active: safetyActive,
      state: safetyActive ? 'CHECKED' : 'STANDBY',
      accent: 'amber' as const,
      note: 'Lipinski rule 4',
    },
  ]

  return (
    <GlassPanel kind="primary" ticks className="relative overflow-hidden p-5 sm:p-7">
      {/* the scan line sweeping the chamber */}
      <span className="pointer-events-none absolute inset-x-0 top-0 h-16 animate-scan-y bg-gradient-to-b from-transparent via-mint/[0.07] to-transparent" />

      <div className="relative mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <Hud className="mb-1.5 block">Specimen</Hud>
          <div className="font-mono text-[16px] font-medium text-ink">{candidate.drug}</div>
        </div>
        <div className="flex items-center gap-2">
          <StatusDot accent={safetyActive ? 'mint' : 'amber'} pulse={false} />
          <Hud className={safetyActive ? 'text-mint' : 'text-amber'}>
            {safetyActive ? 'Full screen' : 'Partial screen'}
          </Hud>
        </div>
      </div>

      <ul className="relative space-y-0">
        {checks.map((c, i) => (
          <motion.li
            key={c.name}
            initial={{ opacity: 0, x: -10 }}
            whileInView={{ opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.5, delay: i * 0.08, ease: [0.22, 1, 0.36, 1] }}
            className={cx(
              'flex items-center justify-between gap-4 border-b border-line/[0.07] py-3 last:border-0',
              !c.active && 'opacity-55',
            )}
          >
            <div className="flex min-w-0 items-center gap-3">
              <span
                className={cx(
                  'flex h-6 w-6 shrink-0 items-center justify-center rounded border text-[10px]',
                  c.active
                    ? c.accent === 'mint'
                      ? 'border-mint/45 text-mint'
                      : c.accent === 'iris'
                        ? 'border-iris/45 text-iris'
                        : 'border-amber/45 text-amber'
                    : 'border-line/20 text-faint',
                )}
              >
                {c.active ? '✓' : '·'}
              </span>
              <div className="min-w-0">
                <div className="truncate text-[13px] text-ink">{c.name}</div>
                <div className="truncate text-[10.5px] text-faint">{c.note}</div>
              </div>
            </div>
            <span
              className={cx(
                'num shrink-0 text-[9.5px] font-semibold uppercase tracking-hud',
                c.active
                  ? c.accent === 'mint'
                    ? 'text-mint'
                    : c.accent === 'iris'
                      ? 'text-iris'
                      : 'text-amber'
                  : 'text-faint',
              )}
            >
              {c.state}
            </span>
          </motion.li>
        ))}
      </ul>

      {!safetyActive && (
        <div className="relative mt-5 rounded-lg border border-amber/30 bg-amber/[0.05] p-4">
          <Hud className="mb-2 block text-amber">Why the Lipinski rules are on standby</Hud>
          <p className="text-[12px] leading-relaxed text-ink text-pretty">
            Computing molecular weight, logP and hydrogen-bond counts requires a cheminformatics
            toolkit and a SMILES structure for every compound. Neither ships with this repository,
            so the screen contributes its neutral 0.50 to the fused score rather than a guessed
            value. Drop a structure descriptor table in and all four rules activate.
          </p>
        </div>
      )}
    </GlassPanel>
  )
}

/**
 * The fused score, broken into the three terms that produced it. Every number
 * shown is read straight off the candidate record, so the bar and the total
 * are the same arithmetic the engine performed.
 */
function ScoreFusion({
  candidate,
  weights,
  safetyActive,
}: {
  candidate: Candidate
  weights: { reversal: number; safety: number; novelty: number }
  safetyActive: boolean
}) {
  const safety = candidate.safetyScore ?? 0.5
  const terms = [
    {
      key: 'Reversal',
      weight: weights.reversal,
      raw: candidate.reversalScaled,
      color: 'bg-mint',
      text: 'text-mint',
      note: 'inverted and min-max scaled across the shortlist',
    },
    {
      key: 'Safety',
      weight: weights.safety,
      raw: safety,
      color: 'bg-amber',
      text: 'text-amber',
      note: safetyActive ? 'Lipinski rules passed' : 'neutral value, screen on standby',
    },
    {
      key: 'Novelty',
      weight: weights.novelty,
      raw: candidate.noveltyBonus,
      color: 'bg-iris',
      text: 'text-iris',
      note: candidate.knownForDisease ? 'known reference bonus' : 'novel candidate baseline',
    },
  ]
  const total = terms.reduce((s, t) => s + t.weight * t.raw, 0)

  return (
    <GlassPanel kind="primary" className="p-5 sm:p-6">
      <div className="mb-4 flex items-baseline justify-between gap-3">
        <Hud>Score fusion</Hud>
        <Provenance kind="computed" />
      </div>

      {/* stacked contribution bar */}
      <div className="mb-5 flex h-3 w-full overflow-hidden rounded-full bg-line/10">
        {terms.map((t) => (
          <motion.span
            key={t.key}
            className={t.color}
            initial={{ width: 0 }}
            whileInView={{ width: `${t.weight * t.raw * 100}%` }}
            viewport={{ once: true }}
            transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
          />
        ))}
      </div>

      <ul className="space-y-3">
        {terms.map((t) => (
          <li key={t.key} className="flex items-start justify-between gap-4">
            <div className="flex min-w-0 items-start gap-2.5">
              <span className={cx('mt-1 h-2 w-2 shrink-0 rounded-full', t.color)} />
              <div className="min-w-0">
                <div className="text-[13px] text-ink">{t.key}</div>
                <div className="text-[10.5px] leading-snug text-faint">{t.note}</div>
              </div>
            </div>
            <div className="shrink-0 text-right">
              <div className="num text-[12px] text-dim">
                {t.weight.toFixed(1)} × {t.raw.toFixed(3)}
              </div>
              <div className={cx('num text-[13px] font-semibold', t.text)}>
                {(t.weight * t.raw).toFixed(3)}
              </div>
            </div>
          </li>
        ))}
      </ul>

      <div className="mt-4 flex items-baseline justify-between border-t border-line/12 pt-4">
        <span className="font-display text-[14px] font-medium text-ink">Final score</span>
        <span className="num text-[22px] font-semibold text-mint">{total.toFixed(4)}</span>
      </div>
    </GlassPanel>
  )
}

function Tally({ label, value, accent }: { label: string; value: number; accent: string }) {
  return (
    <div>
      <div className={cx('font-display text-[30px] font-semibold leading-none', accent)}>
        {value}
      </div>
      <Hud className="mt-2 block">{label}</Hud>
    </div>
  )
}
