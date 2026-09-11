import { AnimatePresence, motion } from 'framer-motion'
import { useEffect, useState } from 'react'
import { cx } from '@/lib/cx'
import type { ScoringMethod } from '@/engine/types'
import { CommandButton } from '@/components/ui/CommandButton'
import { GlassPanel } from '@/components/ui/GlassPanel'
import { Hud } from '@/components/ui/Hud'
import { useApp } from '@/store/useApp'

/**
 * A persistent control dock so the pipeline can be re-run with different
 * settings from anywhere on the page, rather than forcing a scroll back to
 * the hero. It appears once the reader has left the hero, so it never
 * competes with the opening frame.
 */
const METHODS: { id: ScoringMethod; label: string; note: string }[] = [
  {
    id: 'cosine-fast',
    label: 'Cosine · vectorised',
    note: 'Same math as the loop, one pass over the matrix. Default.',
  },
  {
    id: 'cosine',
    label: 'Cosine · per-compound',
    note: 'The original per-column implementation, kept for comparison.',
  },
  {
    id: 'wtcs',
    label: 'WTCS',
    note: 'Rank-based, closer to the original Connectivity Map method. Sensitive to thresholds.',
  },
]

export function ControlDock() {
  const run = useApp((s) => s.run)
  const phase = useApp((s) => s.phase)
  const settings = useApp((s) => s.settings)
  const setSettings = useApp((s) => s.setSettings)
  const result = useApp((s) => s.result)
  const [open, setOpen] = useState(false)
  const [visible, setVisible] = useState(false)

  useEffect(() => {
    const onScroll = () => setVisible(window.scrollY > window.innerHeight * 0.75)
    window.addEventListener('scroll', onScroll, { passive: true })
    onScroll()
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  const busy = phase === 'running' || phase === 'loading'

  return (
    <AnimatePresence>
      {visible && (
        <motion.div
          className="fixed bottom-5 right-5 z-[120] flex flex-col items-end gap-3"
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 24 }}
          transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        >
          <AnimatePresence>
            {open && (
              <motion.div
                initial={{ opacity: 0, y: 12, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: 12, scale: 0.97 }}
                transition={{ duration: 0.28, ease: [0.22, 1, 0.36, 1] }}
                className="w-[320px]"
              >
                <GlassPanel kind="primary" ticks className="p-5">
                  <Hud className="mb-3.5 block">Reversal scoring method</Hud>
                  <div className="space-y-1.5">
                    {METHODS.map((m) => (
                      <button
                        key={m.id}
                        data-cursor="button"
                        onClick={() => setSettings({ method: m.id })}
                        className={cx(
                          'w-full rounded-lg border px-3 py-2.5 text-left transition-colors duration-200',
                          settings.method === m.id
                            ? 'border-mint/50 bg-mint/[0.07]'
                            : 'border-line/12 hover:border-line/28',
                        )}
                      >
                        <div
                          className={cx(
                            'text-[12.5px] font-medium',
                            settings.method === m.id ? 'text-mint' : 'text-ink',
                          )}
                        >
                          {m.label}
                        </div>
                        <div className="mt-0.5 text-[10.5px] leading-snug text-faint">
                          {m.note}
                        </div>
                      </button>
                    ))}
                  </div>

                  <div className="mt-5 space-y-4 border-t border-line/12 pt-4">
                    <Slider
                      label="Candidates displayed"
                      value={settings.displayTopN}
                      min={5}
                      max={40}
                      onChange={(v) => setSettings({ displayTopN: v })}
                    />
                    <Slider
                      label="Validation top-K"
                      value={settings.validationTopK}
                      min={5}
                      max={50}
                      onChange={(v) => setSettings({ validationTopK: v })}
                    />
                  </div>

                  {result && (
                    <p className="mt-4 border-t border-line/12 pt-3 text-[10.5px] leading-relaxed text-faint">
                      Current run used {result.methodLabel}. Changing a setting takes effect on the
                      next run.
                    </p>
                  )}
                </GlassPanel>
              </motion.div>
            )}
          </AnimatePresence>

          <div className="flex items-center gap-2">
            <CommandButton
              size="sm"
              variant="secondary"
              onClick={() => setOpen((o) => !o)}
              aria-label="Pipeline settings"
              title="Pipeline settings"
              className="!px-3"
            >
              <svg width="14" height="14" viewBox="0 0 16 16" fill="none" aria-hidden>
                <circle cx="8" cy="8" r="2.4" stroke="currentColor" strokeWidth="1.3" />
                <path
                  d="M8 1.2v2M8 12.8v2M1.2 8h2M12.8 8h2M3.2 3.2l1.4 1.4M11.4 11.4l1.4 1.4M12.8 3.2l-1.4 1.4M4.6 11.4l-1.4 1.4"
                  stroke="currentColor"
                  strokeWidth="1.3"
                  strokeLinecap="round"
                />
              </svg>
            </CommandButton>
            <CommandButton
              size="sm"
              variant="primary"
              ignite
              disabled={busy}
              onClick={() => void run()}
            >
              {busy ? 'Computing' : result ? 'Re-run pipeline' : 'Initiate discovery'}
            </CommandButton>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  )
}

function Slider({
  label,
  value,
  min,
  max,
  onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  onChange: (v: number) => void
}) {
  return (
    <label className="block">
      <span className="mb-2 flex items-baseline justify-between">
        <Hud>{label}</Hud>
        <span className="num text-[12px] text-mint">{value}</span>
      </span>
      <input
        type="range"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className="h-1 w-full cursor-pointer appearance-none rounded-full bg-line/20 accent-[rgb(var(--c-mint))]"
      />
    </label>
  )
}
