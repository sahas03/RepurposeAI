import { motion, useReducedMotion } from 'framer-motion'
import { cx } from '@/lib/cx'

/**
 * The vertical conduit the pipeline hangs from.
 *
 * Three layers: a dim rail, a mint fill that grows to match completed stages,
 * and a set of particles falling down it. The particles are CSS-animated
 * divs rather than canvas because there are only a dozen of them and this way
 * they cost the main thread nothing per frame.
 */
export function Spine({
  count,
  doneCount,
  running,
}: {
  count: number
  doneCount: number
  running: boolean
}) {
  const reduced = useReducedMotion()
  const progress = count > 0 ? doneCount / count : 0
  const particles = running ? 14 : 6

  return (
    <div
      className="pointer-events-none absolute inset-y-0 left-[27px] w-px lg:left-1/2 lg:-translate-x-1/2"
      aria-hidden="true"
    >
      {/* rail */}
      <div className="absolute inset-0 bg-line/12" />

      {/* completion fill */}
      <motion.div
        className="absolute inset-x-0 top-0 origin-top bg-gradient-to-b from-mint via-mint to-mint/40"
        initial={{ scaleY: 0 }}
        animate={{ scaleY: progress }}
        transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }}
        style={{ height: '100%' }}
      />

      {/* stage markers */}
      {Array.from({ length: count }, (_, i) => {
        const top = `${((i + 0.5) / count) * 100}%`
        const reached = i < doneCount
        return (
          <span
            key={i}
            className={cx(
              'absolute left-1/2 h-2 w-2 -translate-x-1/2 -translate-y-1/2 rotate-45 border transition-colors duration-700',
              reached ? 'border-mint bg-mint' : 'border-line/25 bg-[rgb(var(--c-base))]',
            )}
            style={{ top }}
          />
        )
      })}

      {/* travelling particles */}
      {!reduced &&
        Array.from({ length: particles }, (_, i) => (
          <span
            key={i}
            className="absolute left-1/2 h-6 w-px -translate-x-1/2 bg-gradient-to-b from-transparent via-mint to-transparent"
            style={{
              top: 0,
              opacity: running ? 0.85 : 0.32,
              animation: `spine-fall ${running ? 2.4 : 6.5}s linear ${(i / particles) * (running ? 2.4 : 6.5)}s infinite`,
            }}
          />
        ))}

      <style>{`
        @keyframes spine-fall {
          from { transform: translate(-50%, -6vh); }
          to   { transform: translate(-50%, 100%); }
        }
      `}</style>
    </div>
  )
}
