/**
 * pointer.ts
 * A tiny mutable bus shared between the DOM and the WebGL frame loop.
 *
 * Pointer position and "system energy" change every frame. Routing them
 * through React state would re-render the tree 60 times a second, so they
 * live in a plain module object that r3f reads inside useFrame and the DOM
 * writes from a passive listener. This is the single reason the background
 * can be pointer-reactive without costing the app any renders.
 */

export const pointer = {
  /** Normalised device coords, -1..1. */
  x: 0,
  y: 0,
  /** Smoothed follower, what the scene actually tracks. */
  sx: 0,
  sy: 0,
  /** Page scroll progress, 0..1. */
  scroll: 0,
  /** 0 = idle ambient, 1 = pipeline at full computational load. */
  energy: 0,
  /** Target energy; the frame loop eases towards it. */
  energyTarget: 0,
  /** 1 = dark, 0 = light. Eased so the environment morphs rather than flips. */
  dark: 1,
  darkTarget: 1,
  /** Set while the user hovers the helix - triggers the dormant behaviour. */
  helixDwell: 0,
  /** Halts the render loop when the tab is hidden or the canvas is offscreen. */
  visible: true,
  /** Downgrades particle counts on weak GPUs and small screens. */
  tier: 'high' as 'high' | 'medium' | 'low',
  reducedMotion: false,
}

export function setEnergy(target: number) {
  pointer.energyTarget = Math.max(0, Math.min(1, target))
}

/** Exponential smoothing that stays frame-rate independent. */
export function damp(current: number, target: number, lambda: number, dt: number) {
  return current + (target - current) * (1 - Math.exp(-lambda * dt))
}

export function attachPointerListeners() {
  const onMove = (e: PointerEvent) => {
    pointer.x = (e.clientX / window.innerWidth) * 2 - 1
    pointer.y = -((e.clientY / window.innerHeight) * 2 - 1)
  }
  const onScroll = () => {
    const max = document.documentElement.scrollHeight - window.innerHeight
    pointer.scroll = max > 0 ? window.scrollY / max : 0
  }
  const onVisibility = () => {
    pointer.visible = document.visibilityState === 'visible'
  }

  window.addEventListener('pointermove', onMove, { passive: true })
  window.addEventListener('scroll', onScroll, { passive: true })
  document.addEventListener('visibilitychange', onVisibility)
  onScroll()

  return () => {
    window.removeEventListener('pointermove', onMove)
    window.removeEventListener('scroll', onScroll)
    document.removeEventListener('visibilitychange', onVisibility)
  }
}

/** Cheap capability probe - decides how much geometry the scene can afford. */
export function detectTier(): 'high' | 'medium' | 'low' {
  if (typeof window === 'undefined') return 'medium'
  const cores = navigator.hardwareConcurrency ?? 4
  const w = window.innerWidth
  const coarse = window.matchMedia('(pointer: coarse)').matches

  if (coarse || w < 720) return 'low'
  if (cores <= 4 || w < 1200) return 'medium'
  return 'high'
}
