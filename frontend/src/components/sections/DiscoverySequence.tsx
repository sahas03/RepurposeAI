import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useRef, useState } from 'react'
import { cx } from '@/lib/cx'
import { STAGES } from '@/engine/run'
import { Hud, StatusDot } from '@/components/ui/Hud'
import { CommandButton } from '@/components/ui/CommandButton'
import { useApp } from '@/store/useApp'

/**
 * The computational sequence that replaces a loading spinner.
 *
 * Everything on this screen is a real report from the engine: each stage row
 * fills in only once that stage has actually completed, its readout is the
 * text the stage produced, and the millisecond figure is its measured cost.
 * The overlay is translucent on purpose - the environment behind it visibly
 * spins up as the run progresses.
 */
const EASE = [0.22, 1, 0.36, 1] as const

export function DiscoverySequence() {
  const phase = useApp((s) => s.phase)
  const stages = useApp((s) => s.stages)
  const reports = useApp((s) => s.reports)
  const result = useApp((s) => s.result)
  const error = useApp((s) => s.error)
  const reset = useApp((s) => s.reset)

  const [visible, setVisible] = useState(false)
  const [elapsed, setElapsed] = useState(0)
  const started = useRef(0)

  const active = phase === 'loading' || phase === 'running'

  useEffect(() => {
    if (active && !visible) {
      started.current = performance.now()
      setVisible(true)
    }
  }, [active, visible])

  // Live elapsed clock while the run is in flight.
  useEffect(() => {
    if (!active) return
    let raf = 0
    const tick = () => {
      setElapsed(performance.now() - started.current)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [active])

  // Hold the completion frame briefly, then hand the page over to the results.
  useEffect(() => {
    if (phase !== 'complete' || !visible) return
    const t = window.setTimeout(() => {
      setVisible(false)
      document.getElementById('pipeline')?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }, 2100)
    return () => window.clearTimeout(t)
  }, [phase, visible])

  const done = phase === 'complete'
  const failed = phase === 'error'

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className="fixed inset-0 z-[150] flex items-center justify-center px-5"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0, filter: 'blur(10px)' }}
          transition={{ duration: 0.55, ease: EASE }}
        >
          {/* The veil stays translucent so the universe reacting stays visible. */}
          <motion.div
            className="absolute inset-0 backdrop-blur-xl"
            style={{ background: 'rgb(var(--veil) / 0.82)' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          />

          <motion.div
            className="relative w-full max-w-[720px]"
            initial={{ y: 22, opacity: 0, scale: 0.985 }}
            animate={{ y: 0, opacity: 1, scale: 1 }}
            exit={{ y: -18, opacity: 0, scale: 1.01 }}
            transition={{ duration: 0.6, ease: EASE }}
          >
            <div className="mb-7 flex items-end justify-between gap-4">
              <div>
                <div className="mb-2.5 flex items-center gap-2.5">
                  <StatusDot accent={failed ? 'ember' : done ? 'mint' : 'signal'} pulse={!done} />
                  <Hud className={failed ? 'text-ember' : 'text-mint'}>
                    {failed ? 'Computational interruption' : done ? 'Sequence complete' : 'Sequence running'}
                  </Hud>
                </div>
                <h2 className="font-display text-2xl font-semibold tracking-[-0.03em] sm:text-[28px]">
                  {failed ? 'The run stopped early' : done ? 'Discovery complete' : 'Executing discovery'}
                </h2>
              </div>
              <div className="text-right">
                <Hud className="block">Elapsed</Hud>
                <div className="num mt-1.5 text-[22px] font-semibold text-ink">
                  {(elapsed / 1000).toFixed(2)}
                  <span className="ml-0.5 text-[13px] text-faint">s</span>
                </div>
              </div>
            </div>

            <ol className="relative space-y-0">
              {/* the spine the pulse travels down */}
              <span className="absolute left-[13px] top-3 bottom-3 w-px bg-line/15" />
              {STAGES.map((stage, i) => (
                <StageRow
                  key={stage.id}
                  index={stage.index}
                  title={stage.title}
                  state={stages[stage.id]}
                  readout={reports[stage.id]?.readout}
                  ms={reports[stage.id]?.ms}
                  last={i === STAGES.length - 1}
                />
              ))}
            </ol>

            <AnimatePresence>
              {done && result && (
                <motion.div
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.6, ease: EASE, delay: 0.1 }}
                  className="mt-7 rounded-xl border border-mint/30 bg-mint/[0.05] p-5"
                >
                  <Hud className="mb-2.5 block text-mint">Leading candidate</Hud>
                  <div className="flex flex-wrap items-baseline justify-between gap-3">
                    <span className="font-mono text-[17px] font-medium text-ink">
                      {result.candidates[0]?.drug}
                    </span>
                    <span className="num text-[15px] text-mint">
                      reversal {result.candidates[0]?.reversalScore.toFixed(4)}
                    </span>
                  </div>
                  <p className="mt-3 text-[12px] leading-relaxed text-dim">
                    {result.candidates.length} candidates ranked from {result.drugsScored} compound
                    signatures. Model output on {result.dataset.provenance} data — not a clinical
                    finding.
                  </p>
                </motion.div>
              )}

              {failed && error && (
                <motion.div
                  initial={{ opacity: 0, y: 16 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="mt-7 rounded-xl border border-ember/35 bg-ember/[0.05] p-5"
                >
                  <Hud className="mb-2 block text-ember">Stage · {error.stage}</Hud>
                  <p className="text-[13px] leading-relaxed text-ink">{error.message}</p>
                  <div className="mt-4 flex gap-3">
                    <CommandButton
                      size="sm"
                      variant="secondary"
                      onClick={() => {
                        setVisible(false)
                        reset()
                      }}
                    >
                      Dismiss
                    </CommandButton>
                  </div>
                </motion.div>
              )}
            </AnimatePresence>

            {!done && !failed && (
              <p className="mt-7 text-center text-[11px] text-faint">
                Scoring runs in this page against the repository CSVs. Stage timings shown are
                measured, not simulated.
              </p>
            )}
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function StageRow({
  index,
  title,
  state,
  readout,
  ms,
  last,
}: {
  index: string
  title: string
  state: 'pending' | 'active' | 'done' | 'error'
  readout?: string
  ms?: number
  last: boolean
}) {
  return (
    <li
      className={cx(
        'relative flex gap-4 py-3 transition-opacity duration-500',
        state === 'pending' ? 'opacity-35' : 'opacity-100',
        !last && 'border-b border-line/[0.07]',
      )}
    >
      <span className="relative z-10 mt-0.5 flex h-[27px] w-[27px] shrink-0 items-center justify-center">
        <motion.span
          className={cx(
            'absolute inset-0 rounded-full border',
            state === 'done'
              ? 'border-mint bg-mint/15'
              : state === 'active'
                ? 'border-signal bg-signal/10'
                : state === 'error'
                  ? 'border-ember bg-ember/15'
                  : 'border-line/25 bg-[rgb(var(--glass)/0.5)]',
          )}
          animate={
            state === 'active'
              ? { scale: [1, 1.14, 1], opacity: [1, 0.75, 1] }
              : { scale: 1, opacity: 1 }
          }
          transition={{ duration: 1.3, repeat: state === 'active' ? Infinity : 0, ease: 'easeInOut' }}
        />
        <span
          className={cx(
            'num relative text-[10px] font-semibold',
            state === 'done'
              ? 'text-mint'
              : state === 'active'
                ? 'text-signal'
                : state === 'error'
                  ? 'text-ember'
                  : 'text-faint',
          )}
        >
          {state === 'done' ? '✓' : index}
        </span>
      </span>

      <div className="min-w-0 flex-1">
        <div className="flex items-baseline justify-between gap-3">
          <span className="font-display text-[14px] font-medium tracking-[-0.01em] text-ink">
            {title}
          </span>
          {ms != null && (
            <span className="num shrink-0 text-[10px] text-faint">{ms.toFixed(1)} ms</span>
          )}
        </div>
        <AnimatePresence mode="wait">
          {readout ? (
            <motion.p
              key="readout"
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ duration: 0.4, ease: EASE }}
              className="mt-1 font-mono text-[11px] leading-snug text-mint/80"
            >
              {readout}
            </motion.p>
          ) : state === 'active' ? (
            <motion.p
              key="working"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="mt-1 font-mono text-[11px] text-signal"
            >
              working
              <Ellipsis />
            </motion.p>
          ) : null}
        </AnimatePresence>
      </div>
    </li>
  )
}

function Ellipsis() {
  return (
    <span className="inline-flex">
      {[0, 1, 2].map((i) => (
        <motion.span
          key={i}
          animate={{ opacity: [0.2, 1, 0.2] }}
          transition={{ duration: 1.2, repeat: Infinity, delay: i * 0.18 }}
        >
          .
        </motion.span>
      ))}
    </span>
  )
}
