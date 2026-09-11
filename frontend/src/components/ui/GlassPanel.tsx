import type { CSSProperties, ReactNode } from 'react'
import { useRef, useState } from 'react'
import { cx } from '@/lib/cx'

export type PanelKind = 'primary' | 'secondary' | 'metric' | 'data' | 'warning' | 'evidence'

/**
 * The panel is the app's structural unit, and it deliberately comes in
 * several weights - a metric readout should not carry the same visual mass
 * as the primary result surface. Uniform cards are the fastest way to make a
 * dashboard look like a template, so `kind` changes border, ground and
 * corner treatment, not just padding.
 */
const KIND: Record<PanelKind, string> = {
  primary: 'rounded-2xl border-line/20 bg-[rgb(var(--glass)/calc(var(--glass-a)+0.1))]',
  secondary: 'rounded-xl border-line/12',
  // Metric readouts are square-shouldered: they read as instrument faces.
  metric: 'rounded-md border-line/14',
  // Data surfaces get a hard left edge, like a printed lab record.
  data: 'rounded-r-lg rounded-l-sm border-l-2 border-l-mint/45 border-line/12',
  warning: 'rounded-xl border-amber/35 bg-amber/[0.045]',
  evidence: 'rounded-xl border-dashed border-iris/30 bg-iris/[0.035]',
}

interface Props {
  kind?: PanelKind
  children: ReactNode
  className?: string
  style?: CSSProperties
  /** Adds machined corner ticks. Reserve for surfaces that matter. */
  ticks?: boolean
  /** Subtle pointer-tracked 3D tilt. Off for anything with dense text. */
  tilt?: boolean
  id?: string
}

export function GlassPanel({
  kind = 'secondary',
  children,
  className,
  style,
  ticks,
  tilt,
  id,
}: Props) {
  const ref = useRef<HTMLDivElement>(null)
  const [t, setT] = useState({ rx: 0, ry: 0, mx: 50, my: 50 })

  const onMove = (e: React.PointerEvent) => {
    if (!tilt || !ref.current) return
    const r = ref.current.getBoundingClientRect()
    const px = (e.clientX - r.left) / r.width
    const py = (e.clientY - r.top) / r.height
    setT({ rx: (0.5 - py) * 7, ry: (px - 0.5) * 9, mx: px * 100, my: py * 100 })
  }

  return (
    <div
      id={id}
      ref={ref}
      onPointerMove={onMove}
      onPointerLeave={() => tilt && setT({ rx: 0, ry: 0, mx: 50, my: 50 })}
      className={cx(
        'glass bevel relative isolate',
        KIND[kind],
        ticks && 'ticks',
        tilt && 'transition-transform duration-300 ease-expo will-change-transform',
        className,
      )}
      style={{
        ...style,
        ...(tilt
          ? {
              transform: `perspective(1100px) rotateX(${t.rx}deg) rotateY(${t.ry}deg)`,
            }
          : null),
      }}
    >
      {tilt && (
        // A specular sheen that follows the cursor, so the tilt reads as a
        // physical surface catching light rather than a CSS transform.
        <div
          className="pointer-events-none absolute inset-0 rounded-[inherit] opacity-0 transition-opacity duration-300 [div:hover>&]:opacity-100"
          style={{
            background: `radial-gradient(420px circle at ${t.mx}% ${t.my}%, rgb(var(--c-mint) / 0.09), transparent 60%)`,
          }}
        />
      )}
      {children}
    </div>
  )
}

/** Section-level heading with an index tick and a rule. */
export function SectionHead({
  index,
  eyebrow,
  title,
  lede,
  className,
}: {
  index: string
  eyebrow: string
  title: ReactNode
  lede?: ReactNode
  className?: string
}) {
  return (
    <header className={cx('mb-10', className)}>
      <div className="mb-4 flex items-center gap-3">
        <span className="num text-[11px] font-semibold tracking-wide2 text-mint">{index}</span>
        <span className="h-px w-8 bg-mint/45" />
        <span className="hud">{eyebrow}</span>
      </div>
      <h2 className="max-w-3xl font-display text-3xl font-semibold leading-[1.08] tracking-[-0.03em] text-balance sm:text-4xl lg:text-[2.9rem]">
        {title}
      </h2>
      {lede && (
        <p className="mt-4 max-w-2xl text-[15px] leading-relaxed text-dim text-pretty">{lede}</p>
      )}
    </header>
  )
}
