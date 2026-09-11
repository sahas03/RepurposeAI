import { useMemo } from 'react'
import { cx } from '@/lib/cx'
import { topContributingGenes } from '@/engine/scoring'
import { Drawer } from '@/components/ui/Drawer'
import { GlassPanel } from '@/components/ui/GlassPanel'
import { AnimatedNumber, Hud, Provenance } from '@/components/ui/Hud'
import { useApp, useDetailCandidate } from '@/store/useApp'

/**
 * The full record for one candidate. Everything here is derived from the same
 * run the page is showing - nothing is re-scored, and nothing is asserted that
 * the pipeline did not produce.
 */
export function CandidateDetail() {
  const candidate = useDetailCandidate()
  const closeDetail = useApp((s) => s.closeDetail)
  const result = useApp((s) => s.result)
  const dataset = useApp((s) => s.dataset)

  const open = !!candidate && !!result

  const genes = useMemo(() => {
    if (!dataset || !result || !candidate) return []
    return topContributingGenes(dataset, result.diseaseVec, candidate.drug, 8)
  }, [dataset, result, candidate])

  const rankPct = useMemo(() => {
    if (!result || !candidate) return 0
    const i = result.allScores.findIndex((s) => s.drug === candidate.drug)
    return i < 0 ? 0 : (1 - i / Math.max(1, result.allScores.length - 1)) * 100
  }, [result, candidate])

  return (
    <Drawer
      open={open}
      onClose={closeDetail}
      eyebrow={candidate ? `Candidate ${String(candidate.finalRank).padStart(2, '0')}` : ''}
      title={<span className="font-mono">{candidate?.drug ?? ''}</span>}
      subtitle={
        candidate && (
          <div className="flex flex-wrap items-center gap-2">
            <Provenance kind="computed" />
            <span
              className={cx(
                'rounded-full border px-2.5 py-1 font-mono text-[9px] uppercase tracking-hud',
                candidate.knownForDisease
                  ? 'border-iris/40 text-iris'
                  : 'border-mint/40 text-mint',
              )}
            >
              {candidate.knownForDisease ? 'Known reference' : 'Novel candidate'}
            </span>
          </div>
        )
      }
    >
      {candidate && result && (
        <div className="space-y-7">
          {/* headline score */}
          <GlassPanel kind="primary" ticks className="p-5">
            <Hud className="mb-3 block">Repurposing score</Hud>
            <div className="flex items-end gap-5">
              <span className="font-display text-[46px] font-semibold leading-none tracking-[-0.04em] text-mint">
                <AnimatedNumber value={candidate.finalScore} decimals={4} duration={1.3} />
              </span>
              <div className="pb-2">
                <div className="num text-[12px] text-dim">
                  rank {candidate.finalRank} of {result.candidates.length}
                </div>
                <div className="num text-[11px] text-faint">
                  stronger than {rankPct.toFixed(1)}% of the library
                </div>
              </div>
            </div>
          </GlassPanel>

          <section>
            <Hud className="mb-3 block">Score components</Hud>
            <div className="grid grid-cols-3 gap-3">
              <Component
                label="Reversal"
                value={candidate.reversalScore.toFixed(4)}
                sub={`scaled ${candidate.reversalScaled.toFixed(3)}`}
                accent="text-mint"
              />
              <Component
                label="Safety"
                value={(candidate.safetyScore ?? 0.5).toFixed(2)}
                sub={candidate.safetyScore == null ? 'screen on standby' : 'Lipinski proxy'}
                accent="text-amber"
              />
              <Component
                label="Novelty"
                value={candidate.noveltyBonus.toFixed(1)}
                sub={candidate.knownForDisease ? 'reference bonus' : 'novel baseline'}
                accent="text-iris"
              />
            </div>
          </section>

          <section>
            <Hud className="mb-3 block">Genomic evidence</Hud>
            <GlassPanel kind="data" className="overflow-hidden">
              <table className="w-full border-collapse text-left">
                <thead>
                  <tr className="border-b border-line/12">
                    <th className="px-4 py-2.5">
                      <Hud>Gene</Hud>
                    </th>
                    <th className="px-4 py-2.5">
                      <Hud>Disease z</Hud>
                    </th>
                    <th className="px-4 py-2.5">
                      <Hud>Drug z</Hud>
                    </th>
                    <th className="px-4 py-2.5">
                      <Hud>Product</Hud>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {genes.map((g) => (
                    <tr key={g.gene} className="border-b border-line/[0.06] last:border-0">
                      <td className="px-4 py-2.5 font-mono text-[12px] text-ink">{g.gene}</td>
                      <td className="num px-4 py-2.5 text-[11.5px] text-ember">
                        {g.diseaseLogFC.toFixed(3)}
                      </td>
                      <td className="num px-4 py-2.5 text-[11.5px] text-signal">
                        {g.drugZscore.toFixed(3)}
                      </td>
                      <td
                        className={cx(
                          'num px-4 py-2.5 text-[11.5px]',
                          g.contribution < 0 ? 'text-mint' : 'text-ember',
                        )}
                      >
                        {g.contribution.toFixed(3)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </GlassPanel>
            <p className="mt-2.5 text-[11px] leading-relaxed text-faint">
              Negative products are genes the compound pushes opposite to the disease. Their sum,
              across all {result.genesMatched} shared genes, is the numerator of the cosine score.
            </p>
          </section>

          <section>
            <Hud className="mb-3 block">Mechanism</Hud>
            <GlassPanel kind="warning" className="p-4">
              <p className="text-[12.5px] leading-relaxed text-ink text-pretty">
                No mechanism of action is claimed. This pipeline scores transcriptional similarity
                only — it has no target, pathway or pharmacology data for this compound, and the
                identifier itself is a placeholder from the generated benchmark. Establishing
                mechanism would require a real compound identity plus target annotation.
              </p>
            </GlassPanel>
          </section>

          <section>
            <Hud className="mb-3 block">Validation status</Hud>
            <GlassPanel kind="secondary" className="p-4">
              <p className="text-[12.5px] leading-relaxed text-dim">
                {candidate.knownForDisease
                  ? 'This compound appears in the curated reference set for the target disease. Recovering it is evidence the ranking works, not a new finding.'
                  : result.synthetic?.recovered.includes(candidate.drug)
                    ? 'This is one of the planted reversal signals in the synthetic benchmark. Recovering it near the top is exactly the behaviour the ground-truth check tests for.'
                    : 'No reference status. This compound is neither a curated known drug nor a planted benchmark signal — it is an unlabelled member of the library.'}
              </p>
            </GlassPanel>
          </section>
        </div>
      )}
    </Drawer>
  )
}

function Component({
  label,
  value,
  sub,
  accent,
}: {
  label: string
  value: string
  sub: string
  accent: string
}) {
  return (
    <GlassPanel kind="metric" className="p-3.5">
      <Hud className="mb-2.5 block truncate">{label}</Hud>
      <div className={cx('num text-[17px] font-semibold leading-none', accent)}>{value}</div>
      <div className="mt-1.5 text-[10px] leading-tight text-faint">{sub}</div>
    </GlassPanel>
  )
}
