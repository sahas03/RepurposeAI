import { animate, useInView, useMotionValue } from 'framer-motion'
import type { ReactNode } from 'react'
import { useEffect, useRef, useState } from 'react'
import { cx } from '@/lib/cx'
import { GlassPanel } from './GlassPanel'

/** Small uppercase machine label. The connective tissue of the whole interface. */
export function Hud({ children, className }: { children: ReactNode; className?: string }) {
  return <span className={cx('hud', className)}>{children}</span>
}

/**
 * A number that counts to its value the first time it scrolls into view.
 * Deliberately eases out hard: instruments settle, they do not glide.
 */
export function AnimatedNumber({
  value,
  decimals = 0,
  duration = 1.15,
  suffix = '',
  prefix = '',
  className,
}: {
  value: number
  decimals?: number
  duration?: number
  suffix?: string
  prefix?: string
  className?: string
}) {
  const ref = useRef<HTMLSpanElement>(null)
  const inView = useInView(ref, { once: true, margin: '-8% 0px' })
  const mv = useMotionValue(0)
  const [shown, setShown] = useState(0)

  useEffect(() => {
    if (!inView) return
    const controls = animate(mv, value, {
      duration,
      ease: [0.16, 1, 0.3, 1],
      onUpdate: (v) => setShown(v),
    })
    return () => controls.stop()
  }, [inView, value, duration, mv])

  return (
    <span ref={ref} className={cx('num tabular-nums', className)}>
      {prefix}
      {shown.toFixed(decimals)}
      {suffix}
    </span>
  )
}

export type Accent = 'mint' | 'ember' | 'iris' | 'amber' | 'signal' | 'neutral'

const ACCENT_TEXT: Record<Accent, string> = {
  mint: 'text-mint',
  ember: 'text-ember',
  iris: 'text-iris',
  amber: 'text-amber',
  signal: 'text-signal',
  neutral: 'text-ink',
}

const ACCENT_BG: Record<Accent, string> = {
  mint: 'bg-mint',
  ember: 'bg-ember',
  iris: 'bg-iris',
  amber: 'bg-amber',
  signal: 'bg-signal',
  neutral: 'bg-dim',
}

/** An instrument face: label, large value, and an optional micro-readout. */
export function Metric({
  label,
  value,
  decimals = 0,
  suffix,
  accent = 'mint',
  note,
  text,
  className,
}: {
  label: string
  value?: number
  decimals?: number
  suffix?: string
  accent?: Accent
  note?: string
  /** Use instead of `value` when the readout is not numeric. */
  text?: string
  className?: string
}) {
  return (
    <GlassPanel kind="metric" className={cx('group relative overflow-hidden p-4', className)}>
      <div className="mb-3 flex items-center justify-between gap-2">
        <Hud className="truncate">{label}</Hud>
        <span className={cx('h-1 w-1 shrink-0 rounded-full', ACCENT_BG[accent])} />
      </div>
      <div
        className={cx(
          'font-display text-[26px] font-semibold leading-none tracking-[-0.02em]',
          ACCENT_TEXT[accent],
        )}
      >
        {text ?? (
          <>
            <AnimatedNumber value={value ?? 0} decimals={decimals} />
            {suffix && <span className="ml-0.5 text-[15px] opacity-70">{suffix}</span>}
          </>
        )}
      </div>
      {note && <div className="mt-2 text-[11px] leading-snug text-faint">{note}</div>}
      <span
        className={cx(
          'absolute inset-x-0 bottom-0 h-px scale-x-0 transition-transform duration-500 ease-expo group-hover:scale-x-100',
          ACCENT_BG[accent],
          'opacity-60',
        )}
      />
    </GlassPanel>
  )
}

/** Pulsing status light. `pulse` off means steady, not dead. */
export function StatusDot({ accent = 'mint', pulse = true }: { accent?: Accent; pulse?: boolean }) {
  return (
    <span className="relative inline-flex h-2 w-2 shrink-0">
      {pulse && (
        <span
          className={cx('absolute inset-0 rounded-full animate-pulse-ring', ACCENT_BG[accent])}
        />
      )}
      <span className={cx('relative h-2 w-2 rounded-full', ACCENT_BG[accent])} />
    </span>
  )
}

/**
 * Provenance badge. Every surface showing numbers must be able to say where
 * they came from - this is the component that makes that non-optional.
 */
export function Provenance({
  kind,
  className,
}: {
  kind: 'synthetic' | 'real' | 'uploaded' | 'computed' | 'proxy' | 'standby'
  className?: string
}) {
  const map = {
    synthetic: { label: 'Synthetic data', accent: 'amber' as Accent },
    real: { label: 'Real data', accent: 'mint' as Accent },
    uploaded: { label: 'Uploaded data', accent: 'signal' as Accent },
    computed: { label: 'Model output', accent: 'iris' as Accent },
    proxy: { label: 'Proxy screen', accent: 'amber' as Accent },
    standby: { label: 'Standby', accent: 'neutral' as Accent },
  }[kind]

  return (
    <span
      className={cx(
        'inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1',
        'font-mono text-[9px] font-semibold uppercase tracking-hud',
        'border-current/25',
        ACCENT_TEXT[map.accent],
        className,
      )}
    >
      <span className={cx('h-1 w-1 rounded-full', ACCENT_BG[map.accent])} />
      {map.label}
    </span>
  )
}

/** Horizontal instrument rule used between major bands. */
export function Rule({ className }: { className?: string }) {
  return <div className={cx('rule-h', className)} />
}
