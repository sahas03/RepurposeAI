import { useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import { damp, pointer } from '@/store/pointer'
import { blend, getGlowTexture, mulberry32 } from './palette'

/**
 * The far layers: microscopic debris, volumetric haze and the instrument grid.
 * Nothing here is interactive - its whole job is to establish that the viewer
 * is inside a medium, not in front of a flat page.
 */

/** Two parallax shells of drifting particles. */
export function ParticleField({ tier }: { tier: 'high' | 'medium' | 'low' }) {
  const near = tier === 'high' ? 900 : tier === 'medium' ? 480 : 220
  const far = tier === 'high' ? 1400 : tier === 'medium' ? 700 : 300

  const shells = useMemo(() => {
    const rand = mulberry32(1337)
    const make = (n: number, spread: number, depth: [number, number]) => {
      const pos = new Float32Array(n * 3)
      const phase = new Float32Array(n)
      for (let i = 0; i < n; i++) {
        pos[i * 3] = (rand() * 2 - 1) * spread
        pos[i * 3 + 1] = (rand() * 2 - 1) * spread * 0.66
        pos[i * 3 + 2] = depth[0] + rand() * (depth[1] - depth[0])
        phase[i] = rand() * Math.PI * 2
      }
      const geom = new THREE.BufferGeometry()
      geom.setAttribute('position', new THREE.BufferAttribute(pos, 3))
      return { geom, phase, base: pos.slice(), n }
    }
    return [make(near, 22, [-14, 2]), make(far, 46, [-60, -18])]
  }, [near, far])

  const refs = [useRef<THREE.Points>(null), useRef<THREE.Points>(null)]
  const col = useMemo(() => new THREE.Color(), [])

  useFrame((state, dtRaw) => {
    if (!pointer.visible) return
    const dt = Math.min(dtRaw, 1 / 30)
    const t = state.clock.elapsedTime
    blend(col, 'mint', pointer.dark)

    shells.forEach((shell, si) => {
      const ref = refs[si].current
      if (!ref) return
      const parallax = si === 0 ? 1 : 0.32
      ref.position.x = damp(ref.position.x, -pointer.sx * 2.4 * parallax, 1.4, dt)
      ref.position.y = damp(
        ref.position.y,
        -pointer.sy * 1.7 * parallax + pointer.scroll * 9 * parallax,
        1.4,
        dt,
      )

      // Slow vertical convection, like particles suspended in fluid.
      const pos = ref.geometry.getAttribute('position') as THREE.BufferAttribute
      const arr = pos.array as Float32Array
      const speed = 0.16 + pointer.energy * 0.6
      for (let i = 0; i < shell.n; i++) {
        const i3 = i * 3
        arr[i3 + 1] = shell.base[i3 + 1] + Math.sin(t * 0.22 * speed + shell.phase[i]) * 1.4
        arr[i3] = shell.base[i3] + Math.cos(t * 0.15 * speed + shell.phase[i] * 1.7) * 0.9
      }
      pos.needsUpdate = true

      const mat = ref.material as THREE.PointsMaterial
      mat.color.copy(col)
      mat.opacity = (si === 0 ? 0.4 : 0.24) * (0.35 + pointer.dark * 0.65) + pointer.energy * 0.18
    })
  })

  return (
    <>
      {shells.map((shell, i) => (
        <points key={i} ref={refs[i]} geometry={shell.geom}>
          <pointsMaterial
            map={getGlowTexture()}
            size={i === 0 ? 0.13 : 0.09}
            transparent
            sizeAttenuation
            blending={THREE.AdditiveBlending}
            depthWrite={false}
            toneMapped={false}
          />
        </points>
      ))}
    </>
  )
}

/** Large soft sprites standing in for volumetric light. Three quads, no cost. */
export function Haze() {
  const group = useRef<THREE.Group>(null)
  const mats = [
    useRef<THREE.SpriteMaterial>(null),
    useRef<THREE.SpriteMaterial>(null),
    useRef<THREE.SpriteMaterial>(null),
  ]
  const tmp = useMemo(() => ({ mint: new THREE.Color(), ember: new THREE.Color(), iris: new THREE.Color() }), [])

  const blobs = useMemo(
    () =>
      [
        { pos: [7, 3, -18] as const, scale: 34, key: 'mint' as const },
        { pos: [-11, -5, -26] as const, scale: 42, key: 'iris' as const },
        { pos: [-3, 8, -14] as const, scale: 22, key: 'ember' as const },
      ] as const,
    [],
  )

  useFrame((state, dtRaw) => {
    if (!pointer.visible || !group.current) return
    const dt = Math.min(dtRaw, 1 / 30)
    const t = state.clock.elapsedTime
    blend(tmp.mint, 'mint', pointer.dark)
    blend(tmp.ember, 'ember', pointer.dark)
    blend(tmp.iris, 'iris', pointer.dark)

    group.current.position.x = damp(group.current.position.x, pointer.sx * 1.2, 1, dt)
    group.current.position.y = damp(group.current.position.y, pointer.sy * 0.9, 1, dt)

    blobs.forEach((b, i) => {
      const m = mats[i].current
      if (!m) return
      m.color.copy(tmp[b.key])
      // Haze must nearly vanish in light mode or the clinical look goes muddy.
      const base = pointer.dark * 0.16 + 0.018
      m.opacity = base * (0.7 + Math.sin(t * 0.24 + i * 2) * 0.3) + pointer.energy * 0.06
    })
  })

  return (
    <group ref={group}>
      {blobs.map((b, i) => (
        <sprite key={i} position={b.pos} scale={[b.scale, b.scale, 1]}>
          <spriteMaterial
            ref={mats[i]}
            map={getGlowTexture()}
            transparent
            depthWrite={false}
            depthTest={false}
            blending={THREE.AdditiveBlending}
            toneMapped={false}
          />
        </sprite>
      ))}
    </group>
  )
}

/**
 * A receding measurement grid. Deliberately faint: it should read as the floor
 * of an instrument, and be the first thing your eye stops noticing.
 */
export function GridFloor() {
  const ref = useRef<THREE.LineSegments>(null)
  const col = useMemo(() => new THREE.Color(), [])

  const geom = useMemo(() => {
    const size = 90
    const div = 34
    const step = size / div
    const pts: number[] = []
    for (let i = 0; i <= div; i++) {
      const p = -size / 2 + i * step
      pts.push(-size / 2, 0, p, size / 2, 0, p)
      pts.push(p, 0, -size / 2, p, 0, size / 2)
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.Float32BufferAttribute(pts, 3))
    return g
  }, [])

  useFrame((_, dtRaw) => {
    if (!pointer.visible || !ref.current) return
    const dt = Math.min(dtRaw, 1 / 30)
    blend(col, 'chrome', pointer.dark)
    const mat = ref.current.material as THREE.LineBasicMaterial
    mat.color.copy(col)
    mat.opacity = (0.05 + pointer.dark * 0.05 + pointer.energy * 0.05)
    // Drift the grid forward so the space feels like it has motion through it.
    ref.current.position.z = ((ref.current.position.z + dt * (0.6 + pointer.energy * 2.4)) % 2.65)
    ref.current.position.y = damp(ref.current.position.y, -9 + pointer.scroll * 5, 1.2, dt)
  })

  return (
    <lineSegments ref={ref} geometry={geom} position={[0, -9, 0]}>
      <lineBasicMaterial
        transparent
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        toneMapped={false}
      />
    </lineSegments>
  )
}
