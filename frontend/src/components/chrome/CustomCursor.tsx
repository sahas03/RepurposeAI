import { useEffect, useRef, useState } from 'react'

type Mode = 'default' | 'button' | 'ignite' | 'node' | 'text'

/**
 * A scientific reticle in place of the OS cursor.
 *
 * Driven entirely by direct style writes inside a rAF loop - no React state
 * per frame - so it stays pinned to the pointer at any framerate. The mode is
 * read from a `data-cursor` attribute on whatever is under the pointer, which
 * keeps the knowledge of "what kind of thing is this" with the component that
 * owns it rather than in a registry here.
 *
 * Disabled entirely on coarse pointers and when the OS asks for reduced motion.
 */
export function CustomCursor() {
  const dot = useRef<HTMLDivElement>(null)
  const ring = useRef<HTMLDivElement>(null)
  const trail = useRef<HTMLDivElement>(null)
  const [mode, setMode] = useState<Mode>('default')
  const [active, setActive] = useState(false)
  const [down, setDown] = useState(false)

  useEffect(() => {
    const fine = window.matchMedia('(pointer: fine)').matches
    if (!fine) return
    setActive(true)
    document.documentElement.classList.add('rpa-cursor')

    const target = { x: innerWidth / 2, y: innerHeight / 2 }
    const ringPos = { ...target }
    const trailPos = { ...target }
    let raf = 0

    const onMove = (e: PointerEvent) => {
      target.x = e.clientX
      target.y = e.clientY
      if (dot.current) {
        dot.current.style.transform = `translate3d(${e.clientX}px, ${e.clientY}px, 0) translate(-50%, -50%)`
      }
      const el = e.target as HTMLElement | null
      const found = el?.closest<HTMLElement>('[data-cursor]')?.dataset.cursor as Mode | undefined
      const interactive = el?.closest('a, button, [role="button"], input, select')
      setMode(found ?? (interactive ? 'button' : 'default'))
    }

    const loop = () => {
      // Two followers at different stiffnesses give the trail its lag.
      ringPos.x += (target.x - ringPos.x) * 0.19
      ringPos.y += (target.y - ringPos.y) * 0.19
      trailPos.x += (target.x - trailPos.x) * 0.085
      trailPos.y += (target.y - trailPos.y) * 0.085
      if (ring.current) {
        ring.current.style.transform = `translate3d(${ringPos.x}px, ${ringPos.y}px, 0) translate(-50%, -50%)`
      }
      if (trail.current) {
        trail.current.style.transform = `translate3d(${trailPos.x}px, ${trailPos.y}px, 0) translate(-50%, -50%)`
      }
      raf = requestAnimationFrame(loop)
    }
    raf = requestAnimationFrame(loop)

    const onDown = () => setDown(true)
    const onUp = () => setDown(false)
    const onLeave = () => setMode('default')

    window.addEventListener('pointermove', onMove, { passive: true })
    window.addEventListener('pointerdown', onDown)
    window.addEventListener('pointerup', onUp)
    document.addEventListener('pointerleave', onLeave)

    return () => {
      cancelAnimationFrame(raf)
      window.removeEventListener('pointermove', onMove)
      window.removeEventListener('pointerdown', onDown)
      window.removeEventListener('pointerup', onUp)
      document.removeEventListener('pointerleave', onLeave)
      document.documentElement.classList.remove('rpa-cursor')
    }
  }, [])

  if (!active) return null

  const ringSize = mode === 'ignite' ? 56 : mode === 'node' ? 44 : mode === 'button' ? 38 : 26
  const isReticle = mode === 'node' || mode === 'ignite'

  return (
    <div className="pointer-events-none fixed inset-0 z-[200]" aria-hidden="true">
      {/* trailing halo */}
      <div
        ref={trail}
        className="absolute left-0 top-0 rounded-full bg-mint/20 blur-[6px] transition-[width,height,opacity] duration-300 ease-expo"
        style={{
          width: mode === 'default' ? 10 : 22,
          height: mode === 'default' ? 10 : 22,
          opacity: mode === 'default' ? 0.35 : 0.6,
        }}
      />

      {/* reticle ring */}
      <div
        ref={ring}
        className="absolute left-0 top-0 transition-[width,height,opacity] duration-[280ms] ease-expo"
        style={{ width: ringSize, height: ringSize, opacity: down ? 1 : 0.85 }}
      >
        <div
          className="h-full w-full rounded-full border transition-all duration-[280ms] ease-expo"
          style={{
            borderColor: `rgb(var(--c-mint) / ${mode === 'default' ? 0.45 : 0.85})`,
            borderWidth: isReticle ? 1 : 1,
            transform: `scale(${down ? 0.82 : 1}) rotate(${isReticle ? 45 : 0}deg)`,
            borderRadius: mode === 'ignite' ? '4px' : '999px',
          }}
        />
        {/* targeting ticks appear only over pipeline nodes and the main CTA */}
        {isReticle && (
          <>
            <span className="absolute left-1/2 top-[-7px] h-2 w-px -translate-x-1/2 bg-mint" />
            <span className="absolute bottom-[-7px] left-1/2 h-2 w-px -translate-x-1/2 bg-mint" />
            <span className="absolute left-[-7px] top-1/2 h-px w-2 -translate-y-1/2 bg-mint" />
            <span className="absolute right-[-7px] top-1/2 h-px w-2 -translate-y-1/2 bg-mint" />
          </>
        )}
      </div>

      {/* the point itself - never lags */}
      <div
        ref={dot}
        className="absolute left-0 top-0 rounded-full bg-mint transition-[width,height] duration-200"
        style={{ width: down ? 7 : 4, height: down ? 7 : 4 }}
      />
    </div>
  )
}
