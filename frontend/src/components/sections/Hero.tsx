import { motion, useReducedMotion } from 'framer-motion'
import { DATASETS } from '@/api/client'
import { CommandButton } from '@/components/ui/CommandButton'
import { Hud, Provenance } from '@/components/ui/Hud'
import { useApp } from '@/store/useApp'

/**
 * The opening frame.
 *
 * Choreography is layered rather than sequential: the environment is already
 * moving when the type arrives, so the page never reads as "loading, then
 * content". Total entrance is ~1.6s and nothing blocks interaction during it.
 */

const EASE = [0.22, 1, 0.36, 1] as const

/** Type that arrives by un-clipping upward, like a readout printing. */
function Line({ children, delay }: { children: React.ReactNode; delay: number }) {
  const reduced = useReducedMotion()
  if (reduced) return <span className="block">{children}</span>
  return (
    <span className="block overflow-hidden py-[0.06em]">
      <motion.span
        className="block"
        initial={{ y: '105%', opacity: 0 }}
        animate={{ y: '0%', opacity: 1 }}
        transition={{ duration: 0.95, delay, ease: EASE }}
      >
        {children}
      </motion.span>
    </span>
  )
}

function Fade({
  children,
  delay,
  className,
}: {
  children: React.ReactNode
  delay: number
  className?: string
}) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 14, filter: 'blur(5px)' }}
      animate={{ opacity: 1, y: 0, filter: 'blur(0px)' }}
      transition={{ duration: 0.8, delay, ease: EASE }}
    >
      {children}
    </motion.div>
  )
}

export function Hero() {
  const run = useApp((s) => s.run)
  const phase = useApp((s) => s.phase)
  const busy = phase === 'running' || phase === 'loading'

  return (
    <section
      id="discover"
      className="relative flex min-h-[100svh] items-center px-5 pb-24 pt-32 sm:px-8"
    >
      <HudFrame />

      <div className="relative z-10 mx-auto w-full max-w-[1400px]">
        <div className="max-w-[54rem]">
          <Fade delay={0.15} className="mb-8 flex flex-wrap items-center gap-3">
            <span className="inline-flex items-center gap-2.5 rounded-full border border-mint/25 bg-mint/[0.06] px-3.5 py-1.5">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inset-0 animate-pulse-ring rounded-full bg-mint" />
                <span className="relative h-1.5 w-1.5 rounded-full bg-mint" />
              </span>
              <Hud className="text-mint">Computational drug repurposing</Hud>
            </span>
            <Hud className="text-faint">Target · Rheumatoid arthritis</Hud>
          </Fade>

          <h1 className="font-display text-[clamp(2.6rem,7.4vw,6.1rem)] font-semibold leading-[0.94] tracking-[-0.045em]">
            <Line delay={0.3}>
              <span className="text-ink">Discover what</span>
            </Line>
            <Line delay={0.42}>
              <span className="text-ink">existing drugs</span>
            </Line>
            <Line delay={0.54}>
              <span className="bg-gradient-to-r from-mint via-mint to-signal bg-clip-text text-transparent">
                could become.
              </span>
            </Line>
          </h1>

          <Fade delay={0.8}>
            <p className="mt-8 max-w-[38rem] text-[16px] leading-[1.65] text-dim text-pretty sm:text-[17px]">
              A disease writes a signature into gene expression. RepurposeAI searches a library of
              compound signatures for the one that writes the{' '}
              <em className="not-italic text-ink">opposite</em> — then scores it for safety,
              novelty and evidence, and shows its working gene by gene.
            </p>
          </Fade>

          <Fade delay={0.95} className="mt-10 flex flex-wrap items-center gap-4">
            <CommandButton
              variant="primary"
              size="lg"
              ignite
              disabled={busy}
              onClick={() => void run()}
              className="min-w-[280px]"
            >
              <IgniteIcon />
              {busy ? 'Computing…' : 'Initiate Discovery'}
            </CommandButton>
            <CommandButton variant="ghost" size="lg" onClick={() => scrollToId('pipeline')}>
              Examine the method
              <span aria-hidden className="text-mint">
                ↓
              </span>
            </CommandButton>
          </Fade>

          <Fade delay={1.15} className="mt-14">
            <div className="flex flex-wrap items-center gap-x-10 gap-y-5 border-t border-line/12 pt-6">
              <Stat k="200" label="Signature genes" />
              <Stat k="150" label="Compound signatures" />
              <Stat k="6" label="Pipeline stages" />
              <Stat k="in-page" label="Scoring runtime" mono />
            </div>
          </Fade>

          <Fade delay={1.3} className="mt-6 max-w-[40rem]">
            <div className="flex flex-wrap items-start gap-3">
              <Provenance kind="synthetic" />
              <p className="flex-1 text-[11.5px] leading-relaxed text-faint text-pretty">
                {DATASETS[0].disclosure}
              </p>
            </div>
          </Fade>
        </div>
      </div>

      <ScrollCue />
    </section>
  )
}

function Stat({ k, label, mono }: { k: string; label: string; mono?: boolean }) {
  return (
    <div>
      <div
        className={`${mono ? 'font-mono text-[17px]' : 'font-display text-[26px]'} font-semibold leading-none tracking-[-0.02em] text-ink`}
      >
        {k}
      </div>
      <Hud className="mt-2 block">{label}</Hud>
    </div>
  )
}

function IgniteIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <circle cx="8" cy="8" r="6.5" stroke="currentColor" strokeWidth="1.2" opacity="0.45" />
      <circle cx="8" cy="8" r="2.4" fill="currentColor" />
      <path d="M8 0.5v3M8 12.5v3M0.5 8h3M12.5 8h3" stroke="currentColor" strokeWidth="1.2" />
    </svg>
  )
}

/** Corner coordinates and edge ticks. Frames the viewport as an instrument. */
function HudFrame() {
  return (
    <div className="pointer-events-none absolute inset-0 z-10 hidden lg:block" aria-hidden="true">
      <div className="absolute left-8 top-1/2 -translate-y-1/2 -rotate-90">
        <Hud className="whitespace-nowrap">System 01 · Biocompute</Hud>
      </div>
      <div className="absolute right-8 top-1/2 flex -translate-y-1/2 rotate-90 items-center gap-3">
        <Hud className="whitespace-nowrap">Signature · Vector · Genome</Hud>
      </div>
      <div className="absolute inset-x-8 bottom-8 flex items-end justify-between">
        <Hud>Lat 17.39 · Lon 78.48</Hud>
        <Hud>Rev 1.0 · Frontend</Hud>
      </div>
      {/* edge tick marks */}
      <div className="absolute left-0 top-0 h-full w-px">
        {Array.from({ length: 24 }, (_, i) => (
          <span
            key={i}
            className="absolute left-0 h-px bg-line/25"
            style={{ top: `${(i / 24) * 100}%`, width: i % 4 === 0 ? 12 : 5 }}
          />
        ))}
      </div>
    </div>
  )
}

function ScrollCue() {
  return (
    <motion.div
      className="absolute bottom-8 left-1/2 z-10 hidden -translate-x-1/2 flex-col items-center gap-2 lg:flex"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      transition={{ delay: 1.7, duration: 0.8 }}
    >
      <Hud>Scroll</Hud>
      <span className="relative h-10 w-px overflow-hidden bg-line/20">
        <motion.span
          className="absolute inset-x-0 h-4 bg-mint"
          animate={{ y: [-16, 40] }}
          transition={{ duration: 2.2, repeat: Infinity, ease: 'easeInOut' }}
        />
      </span>
    </motion.div>
  )
}

export function scrollToId(id: string) {
  document.getElementById(id)?.scrollIntoView({ behavior: 'smooth', block: 'start' })
}
