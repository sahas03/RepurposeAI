import { motion } from 'framer-motion'
import { useRef } from 'react'
import { useTheme } from '@/store/useTheme'

/**
 * Not a checkbox: a two-position environment selector.
 *
 * The knob is a small celestial body that travels the track, the track itself
 * carries a starfield in dark and a clinical grid in light, and the actual
 * theme swap rides a circular View Transition expanding from this control
 * (see useTheme). The intent is that the switch is the origin of the change,
 * not just its trigger.
 */
export function ThemeToggle() {
  const { theme, toggle } = useTheme()
  const ref = useRef<HTMLButtonElement>(null)
  const dark = theme === 'dark'

  const onClick = () => {
    const r = ref.current?.getBoundingClientRect()
    toggle(r ? { x: r.left + r.width / 2, y: r.top + r.height / 2 } : undefined)
  }

  return (
    <button
      ref={ref}
      onClick={onClick}
      data-cursor="button"
      role="switch"
      aria-checked={dark}
      aria-label={dark ? 'Switch to clinical light environment' : 'Switch to deep dark environment'}
      title={dark ? 'Light environment' : 'Dark environment'}
      className="group relative h-9 w-[70px] shrink-0 overflow-hidden rounded-full border border-line/20 transition-colors duration-500 hover:border-mint/50 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-mint"
      style={{ contain: 'paint' }}
    >
      {/* track: deep space */}
      <span
        className="absolute inset-0 transition-opacity duration-700 ease-expo"
        style={{
          opacity: dark ? 1 : 0,
          background:
            'radial-gradient(circle at 78% 50%, rgb(var(--c-iris) / 0.30), transparent 60%), linear-gradient(90deg, #060f12, #0a181c)',
        }}
      >
        {STARS.map((s, i) => (
          <span
            key={i}
            className="absolute rounded-full bg-white animate-hud-blink"
            style={{
              left: `${s.x}%`,
              top: `${s.y}%`,
              width: s.r,
              height: s.r,
              opacity: s.o,
              animationDelay: `${i * 0.4}s`,
            }}
          />
        ))}
      </span>

      {/* track: clinical bench */}
      <span
        className="absolute inset-0 transition-opacity duration-700 ease-expo"
        style={{
          opacity: dark ? 0 : 1,
          background:
            'linear-gradient(90deg, #e6f0ee, #f7fbfa), repeating-linear-gradient(90deg, rgb(0 90 76 / 0.10) 0 1px, transparent 1px 7px)',
        }}
      />

      {/* the travelling body */}
      <motion.span
        className="absolute top-1/2 z-10 flex h-[26px] w-[26px] items-center justify-center rounded-full"
        initial={false}
        animate={{ left: dark ? 5 : 39, y: '-50%' }}
        transition={{ type: 'spring', stiffness: 380, damping: 30 }}
        style={{
          background: dark
            ? 'radial-gradient(circle at 34% 30%, #d9fff2, #2de8b0 55%, #0e6a52)'
            : 'radial-gradient(circle at 34% 30%, #fff6e2, #ffcf7a 45%, #e08a1e)',
          boxShadow: dark
            ? '0 0 16px rgb(45 232 176 / 0.7), inset -3px -3px 6px rgb(0 40 32 / 0.55)'
            : '0 0 20px rgb(255 190 90 / 0.75), inset -3px -3px 6px rgb(180 110 20 / 0.35)',
        }}
      >
        {/* craters in dark, corona rays in light */}
        {dark ? (
          <>
            <span className="absolute left-[7px] top-[8px] h-[4px] w-[4px] rounded-full bg-[rgb(6_50_40/0.45)]" />
            <span className="absolute right-[6px] top-[13px] h-[3px] w-[3px] rounded-full bg-[rgb(6_50_40/0.35)]" />
          </>
        ) : (
          Array.from({ length: 8 }, (_, i) => (
            <span
              key={i}
              className="absolute h-[1.5px] w-[5px] rounded-full bg-[rgb(255_200_110/0.9)]"
              style={{ transform: `rotate(${i * 45}deg) translateX(16px)` }}
            />
          ))
        )}
      </motion.span>

      {/* the label that is not currently active, so the affordance is legible */}
      <span
        className="absolute top-1/2 -translate-y-1/2 font-mono text-[8px] font-bold uppercase tracking-hud transition-all duration-500"
        style={{
          left: dark ? 38 : 10,
          color: dark ? 'rgb(141 166 162)' : 'rgb(62 92 88)',
        }}
      >
        {dark ? 'LT' : 'DK'}
      </span>
    </button>
  )
}

const STARS = [
  { x: 22, y: 30, r: 1.5, o: 0.9 },
  { x: 46, y: 62, r: 1, o: 0.6 },
  { x: 62, y: 24, r: 1.5, o: 0.75 },
  { x: 78, y: 70, r: 1, o: 0.5 },
  { x: 88, y: 38, r: 1.5, o: 0.85 },
]
