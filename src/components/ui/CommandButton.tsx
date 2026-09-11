import { motion, useReducedMotion } from 'framer-motion'
import type { ReactNode } from 'react'
import { useRef, useState } from 'react'
import { cx } from '@/lib/cx'

type Variant = 'primary' | 'secondary' | 'ghost' | 'danger'

/**
 * Buttons here are modelled as physical instrument controls: energy sweeps
 * the border on hover, the surface compresses on press, and the primary
 * variant emits particles at the moment of commitment. The point is that a
 * click on "Initiate Discovery" should feel like throwing a switch.
 */
const VARIANT: Record<Variant, string> = {
  primary:
    'bg-mint/[0.10] text-mint border-mint/40 hover:bg-mint/[0.16] hover:border-mint/70 shadow-[0_0_0_1px_rgb(var(--c-mint)/0.10),0_18px_50px_-24px_rgb(var(--c-mint)/0.75)]',
  secondary: 'bg-[rgb(var(--glass)/0.5)] text-ink border-line/18 hover:border-mint/45',
  ghost: 'bg-transparent text-dim border-transparent hover:text-ink hover:bg-line/[0.06]',
  danger: 'bg-ember/[0.09] text-ember border-ember/40 hover:bg-ember/[0.15]',
}

const SIZE = {
  sm: 'h-9 px-4 text-[12px]',
  md: 'h-11 px-6 text-[13px]',
  lg: 'h-[68px] px-10 text-[15px]',
}

interface Props {
  children: ReactNode
  onClick?: (e: React.MouseEvent<HTMLButtonElement>) => void
  variant?: Variant
  size?: keyof typeof SIZE
  disabled?: boolean
  className?: string
  type?: 'button' | 'submit'
  /** Marks the control as a major commitment - adds the particle burst. */
  ignite?: boolean
  title?: string
  'aria-label'?: string
}

export function CommandButton({
  children,
  onClick,
  variant = 'secondary',
  size = 'md',
  disabled,
  className,
  type = 'button',
  ignite,
  title,
  'aria-label': ariaLabel,
}: Props) {
  const reduced = useReducedMotion()
  const [sparks, setSparks] = useState<number[]>([])
  const seq = useRef(0)

  const handle = (e: React.MouseEvent<HTMLButtonElement>) => {
    if (disabled) return
    if (ignite && !reduced) {
      const id = seq.current++
      setSparks((s) => [...s, id])
      window.setTimeout(() => setSparks((s) => s.filter((x) => x !== id)), 900)
    }
    onClick?.(e)
  }

  return (
    <motion.button
      type={type}
      title={title}
      aria-label={ariaLabel}
      disabled={disabled}
      onClick={handle}
      data-cursor={ignite ? 'ignite' : 'button'}
      whileTap={reduced || disabled ? undefined : { scale: 0.975 }}
      transition={{ type: 'spring', stiffness: 620, damping: 30 }}
      className={cx(
        'group relative isolate inline-flex select-none items-center justify-center gap-2.5',
        'overflow-hidden rounded-lg border font-display font-medium uppercase tracking-wide2',
        'transition-colors duration-300 ease-expo',
        'disabled:pointer-events-none disabled:opacity-40',
        'focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint',
        VARIANT[variant],
        SIZE[size],
        className,
      )}
    >
      {/* Energy sweeping through the border on hover. */}
      <span className="pointer-events-none absolute inset-0 overflow-hidden rounded-[inherit]">
        <span className="absolute inset-y-0 -left-1/3 w-1/3 -skew-x-12 bg-gradient-to-r from-transparent via-[rgb(var(--c-hi)/0.14)] to-transparent opacity-0 transition-opacity duration-200 group-hover:animate-energy-sweep group-hover:opacity-100" />
      </span>

      {/* Inner glow that intensifies on hover. */}
      {variant === 'primary' && (
        <span className="pointer-events-none absolute inset-0 rounded-[inherit] bg-[radial-gradient(120%_80%_at_50%_120%,rgb(var(--c-mint)/0.22),transparent_70%)] opacity-60 transition-opacity duration-300 group-hover:opacity-100" />
      )}

      {sparks.map((id) => (
        <Burst key={id} />
      ))}

      <span className="relative z-10 inline-flex items-center gap-2.5">{children}</span>
    </motion.button>
  )
}

/** Twelve particles thrown outward from the centre on commit. */
function Burst() {
  return (
    <span className="pointer-events-none absolute inset-0 z-20">
      {Array.from({ length: 12 }, (_, i) => {
        const a = (i / 12) * Math.PI * 2
        return (
          <motion.span
            key={i}
            className="absolute left-1/2 top-1/2 h-1 w-1 rounded-full bg-mint"
            initial={{ x: 0, y: 0, opacity: 1, scale: 1 }}
            animate={{
              x: Math.cos(a) * (70 + (i % 3) * 26),
              y: Math.sin(a) * (26 + (i % 4) * 8),
              opacity: 0,
              scale: 0.3,
            }}
            transition={{ duration: 0.85, ease: [0.22, 1, 0.36, 1] }}
          />
        )
      })}
    </span>
  )
}
