import { AnimatePresence, motion } from 'framer-motion'
import { cx } from '@/lib/cx'
import { STAGES } from '@/engine/run'
import type { StageId } from '@/engine/run'
import { GlassPanel, SectionHead } from '@/components/ui/GlassPanel'
import { Hud } from '@/components/ui/Hud'
import { Reveal } from '@/components/ui/Reveal'
import { StageIcon } from '@/components/ui/StageIcon'
import { useApp } from '@/store/useApp'
import { Spine } from './Spine'
import { StageDrawer } from './StageDrawer'

/**
 * The pipeline is drawn as a single instrument spine with the six stages
 * hanging off it, not as a row of cards. The spine carries particles at all
 * times and lights up segment by segment as stages complete, so the structure
 * itself reports progress rather than a separate progress bar doing it.
 */
export function PipelineSection() {
  const stages = useApp((s) => s.stages)
  const reports = useApp((s) => s.reports)
  const result = useApp((s) => s.result)
  const phase = useApp((s) => s.phase)
  const setOpenStage = useApp((s) => s.setOpenStage)
  const diagnostics = useApp((s) => s.diagnostics)

  const doneCount = STAGES.filter((s) => stages[s.id] === 'done').length

  return (
    <section id="pipeline" className="relative px-5 py-28 sm:px-8">
      <div className="mx-auto w-full max-w-[1400px]">
        <Reveal>
          <SectionHead
            index="01"
            eyebrow="The method"
            title="A computation, not a lookup table."
            lede="Six stages turn a disease expression profile into a ranked, explained shortlist. Each stage below reports what it actually produced on the current run — hover for the metric, open one for the method."
          />
        </Reveal>

        <div className="relative mt-16">
          <Spine
            count={STAGES.length}
            doneCount={doneCount}
            running={phase === 'running' || phase === 'loading'}
          />

          <ol className="relative space-y-5 pl-[68px] lg:space-y-0 lg:pl-0">
            {STAGES.map((stage, i) => (
              <li
                key={stage.id}
                className={cx(
                  'relative lg:flex lg:min-h-[190px] lg:items-center',
                  i % 2 === 0 ? 'lg:justify-start' : 'lg:justify-end',
                )}
              >
                <Reveal delay={0.05} className="lg:w-[calc(50%-58px)]">
                  <StageCard
                    id={stage.id}
                    index={stage.index}
                    title={stage.title}
                    desc={stage.desc}
                    state={stages[stage.id]}
                    readout={reports[stage.id]?.readout}
                    ms={diagnostics ? reports[stage.id]?.ms : undefined}
                    onOpen={() => setOpenStage(stage.id)}
                    flip={i % 2 !== 0}
                  />
                </Reveal>
              </li>
            ))}
          </ol>

          {/* Terminal node: what the pipeline is actually for. */}
          <Reveal className="relative mt-8 pl-[68px] lg:mt-4 lg:pl-0">
            <div className="lg:mx-auto lg:max-w-[520px]">
              <GlassPanel
                kind="primary"
                ticks
                className="overflow-hidden p-6 text-center lg:p-8"
              >
                <Hud className="mb-3 block text-mint">Output</Hud>
                <div className="font-display text-[26px] font-semibold tracking-[-0.03em] sm:text-[32px]">
                  Therapeutic candidates
                </div>
                <AnimatePresence mode="wait">
                  {result ? (
                    <motion.p
                      key="have"
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      className="mt-3 text-[13px] text-dim"
                    >
                      <span className="num text-mint">{result.candidates.length}</span> ranked from{' '}
                      <span className="num text-ink">{result.drugsScored}</span> compound
                      signatures across{' '}
                      <span className="num text-ink">{result.genesMatched}</span> shared genes.
                    </motion.p>
                  ) : (
                    <motion.p
                      key="empty"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      className="mt-3 text-[13px] text-faint"
                    >
                      Run the pipeline to populate every stage below with live output.
                    </motion.p>
                  )}
                </AnimatePresence>
              </GlassPanel>
            </div>
          </Reveal>
        </div>
      </div>

      <StageDrawer />
    </section>
  )
}

function StageCard({
  id,
  index,
  title,
  desc,
  state,
  readout,
  ms,
  onOpen,
  flip,
}: {
  id: StageId
  index: string
  title: string
  desc: string
  state: 'pending' | 'active' | 'done' | 'error'
  readout?: string
  ms?: number
  onOpen: () => void
  flip: boolean
}) {
  const accent =
    state === 'done'
      ? 'text-mint'
      : state === 'active'
        ? 'text-signal'
        : state === 'error'
          ? 'text-ember'
          : 'text-faint'

  return (
    <button
      onClick={onOpen}
      data-cursor="node"
      aria-label={`Open method detail for ${title}`}
      className="group block w-full text-left"
    >
      <GlassPanel
        kind={state === 'error' ? 'warning' : 'secondary'}
        tilt
        className={cx(
          'relative overflow-hidden p-5 transition-all duration-500 ease-expo sm:p-6',
          'group-hover:border-mint/40 group-hover:shadow-lift',
          state === 'pending' && 'opacity-70',
          flip && 'lg:text-right',
        )}
      >
        {/* the connector stub reaching back to the spine */}
        <span
          className={cx(
            'absolute top-1/2 hidden h-px w-[58px] lg:block',
            flip ? 'right-full' : 'left-full',
            state === 'done' ? 'bg-mint/45' : 'bg-line/18',
          )}
        />

        <div
          className={cx(
            'mb-4 flex items-center gap-3',
            flip && 'lg:flex-row-reverse',
          )}
        >
          <span
            className={cx(
              'flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border transition-colors duration-500',
              state === 'done'
                ? 'border-mint/45 bg-mint/[0.08] text-mint'
                : state === 'active'
                  ? 'border-signal/50 bg-signal/[0.08] text-signal'
                  : 'border-line/16 text-dim',
            )}
          >
            <StageIcon id={id} />
          </span>
          <div className={cx('min-w-0 flex-1', flip && 'lg:text-right')}>
            <div className={cx('flex items-center gap-2', flip && 'lg:justify-end')}>
              <span className="num text-[10px] font-semibold tracking-wide2 text-mint">
                {index}
              </span>
              <Hud className={accent}>{state}</Hud>
            </div>
            <h3 className="mt-1 truncate font-display text-[17px] font-semibold tracking-[-0.02em] text-ink">
              {title}
            </h3>
          </div>
        </div>

        <p className="text-[13px] leading-relaxed text-dim">{desc}</p>

        <AnimatePresence>
          {readout && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: 'auto' }}
              transition={{ duration: 0.5, ease: [0.22, 1, 0.36, 1] }}
              className="overflow-hidden"
            >
              <div className="mt-4 border-t border-line/10 pt-3">
                <Hud className="mb-1.5 block">Live readout</Hud>
                <p className="font-mono text-[11.5px] leading-snug text-mint">{readout}</p>
                {ms != null && (
                  <p className="num mt-1.5 text-[10px] text-faint">measured {ms.toFixed(2)} ms</p>
                )}
              </div>
            </motion.div>
          )}
        </AnimatePresence>

        <span
          className={cx(
            'mt-4 inline-flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-hud transition-colors',
            'text-faint group-hover:text-mint',
          )}
        >
          Method detail
          <span aria-hidden>→</span>
        </span>
      </GlassPanel>
    </button>
  )
}
