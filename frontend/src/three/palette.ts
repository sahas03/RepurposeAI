import * as THREE from 'three'

/**
 * The scene palette mirrors the CSS tokens, but as THREE.Color pairs so the
 * frame loop can interpolate between the two environments. Nothing in the 3D
 * layer reads a CSS variable at runtime - that would force a style recalc
 * every frame - so these two tables are the source of truth for WebGL.
 */
type Pair = [dark: string, light: string]

const PAIRS = {
  /** Disease signal. Warm, pathological. */
  ember: ['#ff7a45', '#d04a1a'] as Pair,
  /** Corrective / reversal signal. Cool, bioluminescent. */
  mint: ['#2de8b0', '#009670'] as Pair,
  /** The model layer. Used sparingly. */
  iris: ['#8a94ff', '#4e58d6'] as Pair,
  signal: ['#4cc9f0', '#0c7aa8'] as Pair,
  /** Structural chrome: helix backbone, bonds, grid. */
  chrome: ['#8fb9b2', '#5c8a83'] as Pair,
  haze: ['#0a1518', '#dfeae8'] as Pair,
  bg: ['#04090b', '#eef3f2'] as Pair,
} satisfies Record<string, Pair>

export type PaletteKey = keyof typeof PAIRS

const cache = new Map<string, [THREE.Color, THREE.Color]>()

function pair(key: PaletteKey): [THREE.Color, THREE.Color] {
  let c = cache.get(key)
  if (!c) {
    c = [new THREE.Color(PAIRS[key][0]), new THREE.Color(PAIRS[key][1])]
    cache.set(key, c)
  }
  return c
}

/** Write the theme-blended colour of `key` into `out`. `dark` is 1..0. */
export function blend(out: THREE.Color, key: PaletteKey, dark: number): THREE.Color {
  const [d, l] = pair(key)
  return out.copy(l).lerp(d, dark)
}

/** A soft radial sprite, generated once. Used for every additive glow. */
let glowTexture: THREE.Texture | null = null
export function getGlowTexture(): THREE.Texture {
  if (glowTexture) return glowTexture
  const size = 128
  const canvas = document.createElement('canvas')
  canvas.width = canvas.height = size
  const ctx = canvas.getContext('2d')!
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2)
  g.addColorStop(0, 'rgba(255,255,255,1)')
  g.addColorStop(0.18, 'rgba(255,255,255,0.72)')
  g.addColorStop(0.45, 'rgba(255,255,255,0.16)')
  g.addColorStop(1, 'rgba(255,255,255,0)')
  ctx.fillStyle = g
  ctx.fillRect(0, 0, size, size)
  glowTexture = new THREE.CanvasTexture(canvas)
  glowTexture.colorSpace = THREE.SRGBColorSpace
  return glowTexture
}

/** Deterministic PRNG so the universe is identical on every reload. */
export function mulberry32(seed: number) {
  return function rand() {
    seed |= 0
    seed = (seed + 0x6d2b79f5) | 0
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}
