import { AnimatePresence, motion } from 'framer-motion'
import { useRef, useState } from 'react'
import { GlassPanel } from '@/components/ui/GlassPanel'
import { Hud, StatusDot } from '@/components/ui/Hud'
import { DATASETS } from '@/api/client'
import { useApp } from '@/store/useApp'

/**
 * The status readout only ever reports state the app can actually observe:
 * whether a dataset has been parsed, whether scoring has run, and whether the
 * Lipinski screen has a descriptor table. It never claims a subsystem is
 * "online" on the strength of nothing.
 */
export function SystemStatus() {
  const phase = useApp((s) => s.phase)
  const dataset = useApp((s) => s.dataset)
  const result = useApp((s) => s.result)
  const diagnostics = useApp((s) => s.diagnostics)
  const toggleDiagnostics = useApp((s) => s.toggleDiagnostics)
  const [open, setOpen] = useState(false)
  const clicks = useRef(0)
  const timer = useRef<number | undefined>(undefined)

  const label =
    phase === 'running' || phase === 'loading'
      ? 'COMPUTING'
      : phase === 'error'
        ? 'FAULT'
        : phase === 'complete'
          ? 'RUN COMPLETE'
          : 'BIOCOMPUTE READY'

  const accent = phase === 'error' ? 'ember' : phase === 'running' ? 'signal' : 'mint'

  const subsystems = [
    {
      name: 'Signature loader',
      state: dataset ? 'READY' : 'IDLE',
      ok: !!dataset,
      note: dataset ? `${dataset.genes.length} genes harmonised` : 'no dataset parsed yet',
    },
    {
      name: 'Drug library',
      state: dataset ? 'LOADED' : 'IDLE',
      ok: !!dataset,
      note: dataset ? `${dataset.drugs.length} compound signatures` : 'awaiting first run',
    },
    {
      name: 'Scoring engine',
      state: result ? 'RUN COMPLETE' : 'READY',
      ok: true,
      note: result ? result.methodLabel : 'cosine reversal, in-page',
    },
    {
      name: 'Lipinski screen',
      state: result?.safetyActive ? 'ACTIVE' : 'STANDBY',
      ok: !!result?.safetyActive,
      note: 'needs a structure descriptor table',
    },
  ]

  // Easter egg: five taps on the status light opens the raw diagnostics strip.
  const onLightClick = () => {
    clicks.current += 1
    window.clearTimeout(timer.current)
    timer.current = window.setTimeout(() => (clicks.current = 0), 1400)
    if (clicks.current >= 5) {
      clicks.current = 0
      toggleDiagnostics()
    }
  }

  return (
    <div
      className="relative"
      onMouseEnter={() => setOpen(true)}
      onMouseLeave={() => setOpen(false)}
    >
      <button
        onClick={onLightClick}
        data-cursor="button"
        aria-label={`System status: ${label}`}
        className="flex items-center gap-2 rounded-full border border-line/16 bg-[rgb(var(--glass)/0.45)] px-3 py-1.5 transition-colors hover:border-mint/40"
      >
        <StatusDot accent={accent} pulse={phase === 'running' || phase === 'loading'} />
        <Hud className="hidden text-ink/70 md:inline">{label}</Hud>
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -6, filter: 'blur(4px)' }}
            animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
            exit={{ opacity: 0, y: -6, filter: 'blur(4px)' }}
            transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
            className="absolute right-0 top-[calc(100%+10px)] z-50 w-[290px]"
          >
            <GlassPanel kind="primary" ticks className="p-4">
              <Hud className="mb-3 block">Subsystems</Hud>
              <ul className="space-y-2.5">
                {subsystems.map((s) => (
                  <li key={s.name} className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-[12px] font-medium text-ink">{s.name}</div>
                      <div className="text-[10px] leading-tight text-faint">{s.note}</div>
                    </div>
                    <span
                      className={`num shrink-0 text-[9px] font-semibold uppercase tracking-hud ${
                        s.ok ? 'text-mint' : 'text-faint'
                      }`}
                    >
                      {s.state}
                    </span>
                  </li>
                ))}
              </ul>
              <div className="mt-3.5 border-t border-line/12 pt-3">
                <Hud className="mb-1.5 block">Dataset</Hud>
                <p className="text-[11px] leading-snug text-dim">
                  {DATASETS[0].label} — every score is computed in-page from the CSVs in this
                  repository. No results are pre-baked.
                </p>
              </div>
              {diagnostics && (
                <p className="mt-3 border-t border-mint/20 pt-2.5 font-mono text-[9px] leading-relaxed text-mint/80">
                  DIAGNOSTIC MODE ENGAGED — raw stage timings now visible in the pipeline HUD.
                </p>
              )}
            </GlassPanel>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
