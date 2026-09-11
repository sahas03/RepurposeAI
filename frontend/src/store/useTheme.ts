import { useCallback, useEffect, useState } from 'react'
import { pointer } from './pointer'

export type Theme = 'dark' | 'light'
const KEY = 'repurposeai.theme'

function initial(): Theme {
  if (typeof window === 'undefined') return 'dark'
  const stored = window.localStorage.getItem(KEY)
  if (stored === 'dark' || stored === 'light') return stored
  // First load follows the OS. Dark is the fallback: this is a lab instrument.
  return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark'
}

/** Applied before React mounts (see index.html) to avoid a first-paint flash. */
export function applyTheme(theme: Theme) {
  document.documentElement.setAttribute('data-theme', theme)
  pointer.darkTarget = theme === 'dark' ? 1 : 0
}

export function useTheme() {
  const [theme, setTheme] = useState<Theme>(initial)

  useEffect(() => {
    applyTheme(theme)
    window.localStorage.setItem(KEY, theme)
  }, [theme])

  // Track the OS only while the user has not made an explicit choice.
  useEffect(() => {
    if (window.localStorage.getItem(KEY)) return
    const mq = window.matchMedia('(prefers-color-scheme: light)')
    const onChange = (e: MediaQueryListEvent) => setTheme(e.matches ? 'light' : 'dark')
    mq.addEventListener('change', onChange)
    return () => mq.removeEventListener('change', onChange)
  }, [])

  /**
   * Toggling paints a circular reveal expanding from the switch itself, so the
   * environment reads as changing state rather than repainting. Falls back to
   * a plain swap where View Transitions are unsupported or motion is reduced.
   */
  const toggle = useCallback(
    (origin?: { x: number; y: number }) => {
      const next: Theme = theme === 'dark' ? 'light' : 'dark'
      const doc = document as Document & {
        startViewTransition?: (cb: () => void) => { ready: Promise<void> }
      }

      if (!origin || !doc.startViewTransition || pointer.reducedMotion) {
        setTheme(next)
        return
      }

      const { x, y } = origin
      const radius = Math.hypot(
        Math.max(x, window.innerWidth - x),
        Math.max(y, window.innerHeight - y),
      )

      const transition = doc.startViewTransition(() => {
        applyTheme(next)
        setTheme(next)
      })

      transition.ready.then(() => {
        document.documentElement.animate(
          {
            clipPath: [`circle(0px at ${x}px ${y}px)`, `circle(${radius}px at ${x}px ${y}px)`],
          },
          {
            duration: 720,
            easing: 'cubic-bezier(0.22, 1, 0.36, 1)',
            pseudoElement: '::view-transition-new(root)',
          },
        )
      })
    },
    [theme],
  )

  return { theme, toggle }
}
