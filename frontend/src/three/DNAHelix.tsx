import { useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import { damp, pointer } from '@/store/pointer'
import { blend, getGlowTexture, mulberry32 } from './palette'

/**
 * The signature object: a double helix the user is effectively standing inside.
 *
 * Built from four cheap pieces rather than one expensive one -
 *   two tube backbones, one instanced set of base spheres, one LineSegments
 *   of base pairs, one Points system of travellers -
 * which keeps the whole thing at five draw calls while still reading as a
 * dense, lit molecular structure.
 *
 * It responds to three inputs: the pointer (the helix leans toward the
 * cursor), scroll (it recedes into depth as content takes over), and pipeline
 * energy (base pairs brighten and travellers accelerate during a run).
 */

/** A helix strand as a parametric curve, so TubeGeometry can follow it. */
class HelixCurve extends THREE.Curve<THREE.Vector3> {
  radius: number
  height: number
  turns: number
  phase: number

  constructor(radius: number, height: number, turns: number, phase: number) {
    super()
    this.radius = radius
    this.height = height
    this.turns = turns
    this.phase = phase
  }
  override getPoint(t: number, target = new THREE.Vector3()) {
    const a = t * Math.PI * 2 * this.turns + this.phase
    return target.set(
      Math.cos(a) * this.radius,
      (t - 0.5) * this.height,
      Math.sin(a) * this.radius,
    )
  }
}

interface Props {
  tier: 'high' | 'medium' | 'low'
}

export function DNAHelix({ tier }: Props) {
  const RADIUS = 2.15
  const HEIGHT = 46
  const TURNS = 7.5

  const rungCount = tier === 'high' ? 132 : tier === 'medium' ? 88 : 52
  const travellerCount = tier === 'high' ? 90 : tier === 'medium' ? 56 : 28

  const group = useRef<THREE.Group>(null)
  const inner = useRef<THREE.Group>(null)
  const bases = useRef<THREE.InstancedMesh>(null)
  const rungs = useRef<THREE.LineSegments>(null)
  const travellers = useRef<THREE.Points>(null)
  const tubeA = useRef<THREE.Mesh>(null)
  const tubeB = useRef<THREE.Mesh>(null)

  const curves = useMemo(
    () => [
      new HelixCurve(RADIUS, HEIGHT, TURNS, 0),
      new HelixCurve(RADIUS, HEIGHT, TURNS, Math.PI),
    ],
    [],
  )

  const geoms = useMemo(() => {
    const seg = tier === 'low' ? 180 : 420
    return curves.map((c) => new THREE.TubeGeometry(c, seg, 0.075, 6, false))
  }, [curves, tier])

  /** Base-pair anchor points, reused by the spheres, rungs and travellers. */
  const anchors = useMemo(() => {
    const a: THREE.Vector3[] = []
    const b: THREE.Vector3[] = []
    for (let i = 0; i < rungCount; i++) {
      const t = i / (rungCount - 1)
      a.push(curves[0].getPoint(t, new THREE.Vector3()))
      b.push(curves[1].getPoint(t, new THREE.Vector3()))
    }
    return { a, b }
  }, [curves, rungCount])

  const rungGeom = useMemo(() => {
    const pos = new Float32Array(rungCount * 6)
    const col = new Float32Array(rungCount * 6)
    for (let i = 0; i < rungCount; i++) {
      anchors.a[i].toArray(pos, i * 6)
      anchors.b[i].toArray(pos, i * 6 + 3)
    }
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(pos, 3))
    g.setAttribute('color', new THREE.BufferAttribute(col, 3))
    return g
  }, [anchors, rungCount])

  /**
   * Travellers are particles walking the helix path: they read as information
   * moving along the strand rather than as decorative dust.
   */
  const travelState = useMemo(() => {
    const rand = mulberry32(7717)
    const offsets = new Float32Array(travellerCount)
    const strand = new Float32Array(travellerCount)
    const speed = new Float32Array(travellerCount)
    for (let i = 0; i < travellerCount; i++) {
      offsets[i] = rand()
      strand[i] = rand() < 0.5 ? 0 : 1
      speed[i] = 0.012 + rand() * 0.03
    }
    const geom = new THREE.BufferGeometry()
    geom.setAttribute('position', new THREE.BufferAttribute(new Float32Array(travellerCount * 3), 3))
    return { offsets, strand, speed, geom }
  }, [travellerCount])

  const tmp = useMemo(
    () => ({
      m: new THREE.Matrix4(),
      v: new THREE.Vector3(),
      mint: new THREE.Color(),
      ember: new THREE.Color(),
      chrome: new THREE.Color(),
      mix: new THREE.Color(),
    }),
    [],
  )

  useFrame((_, dtRaw) => {
    if (!pointer.visible) return
    const dt = Math.min(dtRaw, 1 / 30)
    const t = performance.now() / 1000
    const { energy, dark } = pointer

    blend(tmp.mint, 'mint', dark)
    blend(tmp.ember, 'ember', dark)
    blend(tmp.chrome, 'chrome', dark)

    // --- whole-helix motion -------------------------------------------------
    if (group.current && inner.current) {
      // Extremely slow base rotation; energy adds a little urgency.
      inner.current.rotation.y += dt * (0.045 + energy * 0.1)

      // Lean toward the cursor. Small numbers on purpose: it should register
      // as the environment noticing you, not as a joystick.
      const g = group.current
      g.rotation.z = damp(g.rotation.z, pointer.sx * 0.1, 2.2, dt)
      g.rotation.x = damp(g.rotation.x, -pointer.sy * 0.13, 2.2, dt)

      // Recede into depth as the user scrolls into the content.
      const s = pointer.scroll
      g.position.z = damp(g.position.z, -11 - s * 26, 1.6, dt)
      g.position.x = damp(g.position.x, 8.6 + pointer.sx * 1.4 + s * 3.5, 1.8, dt)
      g.position.y = damp(g.position.y, -1 + s * 12, 1.6, dt)
      const scale = 1 - s * 0.18
      g.scale.setScalar(damp(g.scale.x, scale, 1.6, dt))
    }

    // --- backbones ----------------------------------------------------------
    for (const ref of [tubeA, tubeB]) {
      const mat = ref.current?.material as THREE.MeshStandardMaterial | undefined
      if (!mat) return
      mat.color.copy(tmp.chrome)
      mat.emissive.copy(tmp.mint)
      mat.emissiveIntensity = (0.18 + energy * 0.5) * (0.35 + dark * 0.65)
      mat.opacity = 0.5 + dark * 0.35
    }

    // --- base pairs: instanced spheres --------------------------------------
    if (bases.current) {
      for (let i = 0; i < rungCount; i++) {
        const phase = Math.sin(t * 1.4 + i * 0.42)
        const pulse = 1 + phase * (0.1 + energy * 0.3)
        for (let s = 0; s < 2; s++) {
          const p = s === 0 ? anchors.a[i] : anchors.b[i]
          tmp.m.makeScale(pulse, pulse, pulse).setPosition(p)
          bases.current.setMatrixAt(i * 2 + s, tmp.m)
        }
      }
      bases.current.instanceMatrix.needsUpdate = true
      const mat = bases.current.material as THREE.MeshStandardMaterial
      mat.emissive.copy(tmp.mint)
      mat.emissiveIntensity = 0.5 + energy * 1.5
      mat.color.copy(tmp.mint).lerp(tmp.chrome, 0.45)
    }

    // --- base-pair rungs: the two-pole colour language ----------------------
    if (rungs.current) {
      const col = rungs.current.geometry.getAttribute('color') as THREE.BufferAttribute
      const arr = col.array as Float32Array
      // Travelling brightness wave, so the strand reads as carrying signal.
      for (let i = 0; i < rungCount; i++) {
        const wave = 0.5 + 0.5 * Math.sin(i * 0.3 - t * (0.9 + energy * 2.6))
        // Alternate the poles along the strand: disease vs corrective.
        tmp.mix.copy(i % 2 === 0 ? tmp.mint : tmp.ember)
        const k = (0.1 + wave * 0.55) * (0.4 + energy * 0.9) * (0.3 + dark * 0.7)
        for (let v = 0; v < 2; v++) {
          const o = i * 6 + v * 3
          arr[o] = tmp.mix.r * k
          arr[o + 1] = tmp.mix.g * k
          arr[o + 2] = tmp.mix.b * k
        }
      }
      col.needsUpdate = true
    }

    // --- travellers ---------------------------------------------------------
    if (travellers.current) {
      const pos = travellers.current.geometry.getAttribute('position') as THREE.BufferAttribute
      const arr = pos.array as Float32Array
      const boost = 0.35 + energy * 2.1
      for (let i = 0; i < travellerCount; i++) {
        travelState.offsets[i] = (travelState.offsets[i] + travelState.speed[i] * boost * dt) % 1
        const curve = curves[travelState.strand[i]]
        curve.getPoint(travelState.offsets[i], tmp.v)
        tmp.v.toArray(arr, i * 3)
      }
      pos.needsUpdate = true
      const mat = travellers.current.material as THREE.PointsMaterial
      mat.color.copy(tmp.mint)
      mat.opacity = 0.3 + energy * 0.6
      mat.size = 0.3 + energy * 0.34
    }
  })

  return (
    <group ref={group} position={[8.6, -1, -11]}>
      <group ref={inner}>
        <mesh ref={tubeA} geometry={geoms[0]}>
          <meshStandardMaterial
            transparent
            roughness={0.35}
            metalness={0.5}
            toneMapped={false}
          />
        </mesh>
        <mesh ref={tubeB} geometry={geoms[1]}>
          <meshStandardMaterial
            transparent
            roughness={0.35}
            metalness={0.5}
            toneMapped={false}
          />
        </mesh>

        <instancedMesh ref={bases} args={[undefined, undefined, rungCount * 2]}>
          <sphereGeometry args={[0.16, tier === 'low' ? 6 : 10, tier === 'low' ? 6 : 10]} />
          <meshStandardMaterial roughness={0.25} metalness={0.1} toneMapped={false} />
        </instancedMesh>

        <lineSegments ref={rungs} geometry={rungGeom}>
          <lineBasicMaterial
            vertexColors
            transparent
            blending={THREE.AdditiveBlending}
            depthWrite={false}
            toneMapped={false}
          />
        </lineSegments>

        <points ref={travellers} geometry={travelState.geom}>
          <pointsMaterial
            map={getGlowTexture()}
            transparent
            sizeAttenuation
            blending={THREE.AdditiveBlending}
            depthWrite={false}
            toneMapped={false}
          />
        </points>
      </group>
    </group>
  )
}
