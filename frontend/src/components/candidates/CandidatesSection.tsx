import { AnimatePresence, motion } from 'framer-motion'
import { cx } from '@/lib/cx'
import type { Candidate } from '@/engine/types'
import { CommandButton } from '@/components/ui/CommandButton'
import { GlassPanel, SectionHead } from '@/components/ui/GlassPanel'
import { Hud, Provenance } from '@/components/ui/Hud'
import { Reveal } from '@/components/ui/Reveal'
import { useApp } from '@/store/useApp'
import { EmptyField } from '@/components/sections/SignatureSection'
import { CandidateField } from './CandidateField'
import { CandidateDetail } from './CandidateDetail'

/**
 * Three ways to read the same shortlist, because three different people need
 * it: the field for someone seeing it for the first time, the list for
 * scanning, the table for anyone who wants the raw numbers out.
 */
const VIEWS = [
  { id: 'field', label: 'Constellation' },
  { id: 'list', label: 'Ranked' },
  { id: 'table', label: 'Table' },
] as const

export function CandidatesSection() {
  const result = useApp((s) => s.result)
  const view = useApp((s) => s.candidateView)
  const setView = useApp((s) => s.setCandidateView)
  const selected = useApp((s) => s.selected)
  const openDetail = useApp((s) => s.openDetail)
  const settings = useApp((s) => s.settings)

  const shown = result?.candidates.slice(0, settings.displayTopN) ?? []

  return (
    <section id="candidates" className="relative px-5 py-28 sm:px-8">
      <div className="mx-auto w-full max-w-[1400px]">
        <Reveal>
          <SectionHead
            index="06"
            eyebrow="Ranked output"
            title="Therapeutic candidates."
            lede="Ordered by the fused score, with known reference drugs kept in place rather than filtered out. Open any candidate for its full record — reversal, screening, gene-level evidence and its position in the library."
          />
        </Reveal>

        {!result ? (
          <EmptyField label="No candidates yet" />
        ) : (
          <>
            <Reveal className="mb-5">
              <div className="flex flex-wrap items-center justify-between gap-4">
                <div className="flex items-center gap-1 rounded-lg border border-line/14 bg-[rgb(var(--glass)/0.4)] p-1">
                  {VIEWS.map((v) => (
                    <button
                      key={v.id}
                      data-cursor="button"
                      onClick={() => setView(v.id)}
                      className={cx(
                        'relative rounded-md px-3.5 py-2 font-display text-[11.5px] font-medium uppercase tracking-wide2 transition-colors duration-300',
                        view === v.id ? 'text-base' : 'text-dim hover:text-ink',
                      )}
                    >
                      {view === v.id && (
                        <motion.span
                          layoutId="cand-view"
                          className="absolute inset-0 rounded-md bg-mint"
                          transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                        />
                      )}
                      <span className="relative">{v.label}</span>
                    </button>
                  ))}
                </div>

                <div className="flex flex-wrap items-center gap-3">
                  <Provenance kind="computed" />
                  <Hud className="text-faint">
                    showing {shown.length} of {result.candidates.length}
                  </Hud>
                  <CommandButton size="sm" variant="secondary" onClick={() => downloadCsv(result.candidates)}>
                    Export CSV
                  </CommandButton>
                </div>
              </div>
            </Reveal>

            <AnimatePresence mode="wait">
              <motion.div
                key={view}
                initial={{ opacity: 0, y: 14, filter: 'blur(6px)' }}
                animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
                exit={{ opacity: 0, y: -10, filter: 'blur(6px)' }}
                transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
              >
                {view === 'field' && (
                  <GlassPanel kind="primary" ticks className="p-4 sm:p-6">
                    <CandidateField
                      candidates={shown}
                      selected={selected}
                      onSelect={openDetail}
                    />
                  </GlassPanel>
                )}
                {view === 'list' && <RankedList candidates={shown} onSelect={openDetail} selected={selected} />}
                {view === 'table' && <DataTable candidates={shown} onSelect={openDetail} />}
              </motion.div>
            </AnimatePresence>

            <Reveal className="mt-6">
              <GlassPanel kind="evidence" className="p-5">
                <Hud className="mb-2.5 block">What these numbers are</Hud>
                <p className="max-w-4xl text-[12px] leading-relaxed text-dim text-pretty">
                  Every value is model output computed in this page from the repository&rsquo;s{' '}
                  {result.dataset.provenance} benchmark — not a clinical result, not a literature
                  claim and not a prediction about any real compound. Compound identifiers in this
                  dataset are placeholders. The pipeline&rsquo;s purpose is to demonstrate that
                  the ranking math recovers a known signal; the validation panel below is where
                  that is tested.
                </p>
              </GlassPanel>
            </Reveal>
          </>
        )}
      </div>

      <CandidateDetail />
    </section>
  )
}

function RankedList({
  candidates,
  selected,
  onSelect,
}: {
  candidates: Candidate[]
  selected: string | null
  onSelect: (d: string) => void
}) {
  const max = Math.max(...candidates.map((c) => c.finalScore), 1e-9)

  return (
    <div className="space-y-2">
      {candidates.map((c, i) => (
        <motion.button
          key={c.drug}
          data-cursor="node"
          onClick={() => onSelect(c.drug)}
          initial={{ opacity: 0, x: -14 }}
          whileInView={{ opacity: 1, x: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.5, delay: i * 0.04, ease: [0.22, 1, 0.36, 1] }}
          className="block w-full text-left"
        >
          <GlassPanel
            kind={c.knownForDisease ? 'evidence' : 'data'}
            className={cx(
              'group relative overflow-hidden p-4 transition-all duration-300',
              'hover:border-mint/45 hover:shadow-lift',
              selected === c.drug && 'border-mint/60',
            )}
          >
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2.5">
              <span
                className={cx(
                  'num flex h-9 w-9 shrink-0 items-center justify-center rounded-md border text-[12px] font-semibold',
                  i === 0
                    ? 'border-mint bg-mint/15 text-mint'
                    : 'border-line/18 text-dim',
                )}
              >
                {c.finalRank}
              </span>

              <span className="min-w-[150px] flex-1 truncate font-mono text-[14px] text-ink">
                {c.drug}
              </span>

              {c.knownForDisease && (
                <span className="shrink-0 rounded-full border border-iris/35 px-2.5 py-0.5 font-mono text-[9px] uppercase tracking-hud text-iris">
                  Known reference
                </span>
              )}

              <span className="hidden w-[130px] shrink-0 sm:block">
                <Hud className="block">Reversal</Hud>
                <span
                  className={cx(
                    'num text-[12.5px]',
                    c.reversalScore < 0 ? 'text-mint' : 'text-ember',
                  )}
                >
                  {c.reversalScore.toFixed(4)}
                </span>
              </span>

              <span className="hidden w-[90px] shrink-0 md:block">
                <Hud className="block">Safety</Hud>
                <span className="num text-[12.5px] text-amber">
                  {c.safetyScore == null ? '0.50' : c.safetyScore.toFixed(2)}
                  {c.safetyScore == null && <span className="ml-1 text-[9px] text-faint">n/a</span>}
                </span>
              </span>

              <span className="ml-auto shrink-0 text-right">
                <Hud className="block">Fused score</Hud>
                <span className="num text-[16px] font-semibold text-mint">
                  {c.finalScore.toFixed(4)}
                </span>
              </span>
            </div>

            {/* score bar along the bottom edge */}
            <motion.span
              className="absolute inset-x-0 bottom-0 h-[2px] origin-left bg-mint/60"
              initial={{ scaleX: 0 }}
              whileInView={{ scaleX: c.finalScore / max }}
              viewport={{ once: true }}
              transition={{ duration: 0.8, delay: i * 0.04, ease: [0.22, 1, 0.36, 1] }}
            />
          </GlassPanel>
        </motion.button>
      ))}
    </div>
  )
}

function DataTable({
  candidates,
  onSelect,
}: {
  candidates: Candidate[]
  onSelect: (d: string) => void
}) {
  const cols = [
    'Rank',
    'Compound',
    'Reversal',
    'Scaled',
    'Safety',
    'Novelty',
    'Fused',
    'Label',
  ]
  return (
    <GlassPanel kind="primary" className="overflow-x-auto">
      <table className="w-full min-w-[820px] border-collapse text-left">
        <thead>
          <tr className="border-b border-line/14">
            {cols.map((c) => (
              <th key={c} className="px-4 py-3.5 first:pl-6 last:pr-6">
                <Hud>{c}</Hud>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {candidates.map((c) => (
            <tr
              key={c.drug}
              data-cursor="node"
              onClick={() => onSelect(c.drug)}
              className="cursor-pointer border-b border-line/[0.06] transition-colors last:border-0 hover:bg-mint/[0.05]"
            >
              <td className="num px-4 py-3 pl-6 text-[12px] text-dim">{c.finalRank}</td>
              <td className="px-4 py-3 font-mono text-[12.5px] text-ink">{c.drug}</td>
              <td
                className={cx(
                  'num px-4 py-3 text-[12px]',
                  c.reversalScore < 0 ? 'text-mint' : 'text-ember',
                )}
              >
                {c.reversalScore.toFixed(4)}
              </td>
              <td className="num px-4 py-3 text-[12px] text-dim">
                {c.reversalScaled.toFixed(3)}
              </td>
              <td className="num px-4 py-3 text-[12px] text-amber">
                {(c.safetyScore ?? 0.5).toFixed(2)}
              </td>
              <td className="num px-4 py-3 text-[12px] text-iris">{c.noveltyBonus.toFixed(1)}</td>
              <td className="num px-4 py-3 text-[13px] font-semibold text-mint">
                {c.finalScore.toFixed(4)}
              </td>
              <td className="px-4 py-3 pr-6 text-[11px] text-faint">{c.noveltyLabel}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </GlassPanel>
  )
}

function downloadCsv(candidates: Candidate[]) {
  const header = [
    'final_rank',
    'drug',
    'reversal_score',
    'reversal_scaled',
    'safety_score',
    'novelty_bonus',
    'final_score',
    'known_for_disease',
    'novelty_label',
  ]
  const rows = candidates.map((c) =>
    [
      c.finalRank,
      c.drug,
      c.reversalScore,
      c.reversalScaled,
      c.safetyScore ?? '',
      c.noveltyBonus,
      c.finalScore,
      c.knownForDisease,
      `"${c.noveltyLabel}"`,
    ].join(','),
  )
  const blob = new Blob([[header.join(','), ...rows].join('\n')], { type: 'text/csv' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'repurposeai_candidates.csv'
  a.click()
  URL.revokeObjectURL(url)
}
