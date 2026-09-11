import { useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import { damp, pointer } from '@/store/pointer'
import { blend, mulberry32 } from './palette'

/**
 * Abstract molecular structures drifting at three depths.
 *
 * These are procedural geometries, not depictions of specific compounds -
 * the app never claims otherwise. They exist to give the space physical
 * scale and parallax: near ones are large and slow, far ones small and dim.
 *
 * All atoms across all molecules live in ONE InstancedMesh and all bonds in
 * ONE LineSegments, so the entire field costs two draw calls.
 */

interface Molecule {
  center: THREE.Vector3
  drift: THREE.Vector3
  spin: THREE.Vector3
  rot: THREE.Euler
  atoms: THREE.Vector3[]
  /** Pre-allocated world-space mirror of `atoms`, refilled each frame. */
  world: THREE.Vector3[]
  bonds: [number, number][]
  radius: number
  /** 0 = mint pole, 1 = ember pole. Fixed per molecule. */
  pole: number
}

function buildMolecule(rand: () => number, scale: number): Pick<Molecule, 'atoms' | 'bonds'> {
  const n = 4 + Math.floor(rand() * 5)
  const atoms: THREE.Vector3[] = [new THREE.Vector3(0, 0, 0)]
  const bonds: [number, number][] = []

  // Grow outward from a seed atom, always bonding to an existing one, which
  // produces connected, plausible-looking skeletons rather than clouds.
  for (let i = 1; i < n; i++) {
    const parent = Math.floor(rand() * atoms.length)
    const dir = new THREE.Vector3(rand() * 2 - 1, rand() * 2 - 1, rand() * 2 - 1).normalize()
    atoms.push(dir.multiplyScalar(scale * (0.7 + rand() * 0.5)).add(atoms[parent]))
    bonds.push([parent, i])
  }
  // A ring closure on some molecules reads as far more chemical than a tree.
  if (rand() > 0.45 && n > 4) bonds.push([n - 1, Math.floor(rand() * 2)])
  return { atoms, bonds }
}

interface Props {
  tier: 'high' | 'medium' | 'low'
}

export function MoleculeField({ tier }: Props) {
  const count = tier === 'high' ? 16 : tier === 'medium' ? 10 : 5

  const atomsRef = useRef<THREE.InstancedMesh>(null)
  const bondsRef = useRef<THREE.LineSegments>(null)
  const group = useRef<THREE.Group>(null)

  const { molecules, totalAtoms, totalBonds } = useMemo(() => {
    const rand = mulberry32(4242)
    const mols: Molecule[] = []
    for (let i = 0; i < count; i++) {
      const depth = rand()
      const scale = 0.32 + depth * 0.55
      const { atoms, bonds } = buildMolecule(rand, scale)
      mols.push({
        center: new THREE.Vector3(
          (rand() * 2 - 1) * 16,
          (rand() * 2 - 1) * 11,
          -4 - depth * 22,
        ),
        drift: new THREE.Vector3(rand() * 2 - 1, rand() * 2 - 1, 0).multiplyScalar(0.05),
        spin: new THREE.Vector3(rand() - 0.5, rand() - 0.5, rand() - 0.5).multiplyScalar(0.16),
        rot: new THREE.Euler(rand() * 6, rand() * 6, rand() * 6),
        atoms,
        world: atoms.map(() => new THREE.Vector3()),
        bonds,
        radius: scale,
        pole: rand() < 0.32 ? 1 : 0,
      })
    }
    return {
      molecules: mols,
      totalAtoms: mols.reduce((s, m) => s + m.atoms.length, 0),
      totalBonds: mols.reduce((s, m) => s + m.bonds.length, 0),
    }
  }, [count])

  const bondGeom = useMemo(() => {
    const g = new THREE.BufferGeometry()
    g.setAttribute('position', new THREE.BufferAttribute(new Float32Array(totalBonds * 6), 3))
    g.setAttribute('color', new THREE.BufferAttribute(new Float32Array(totalBonds * 6), 3))
    return g
  }, [totalBonds])

  const tmp = useMemo(
    () => ({
      m: new THREE.Matrix4(),
      q: new THREE.Quaternion(),
      e: new THREE.Euler(),
      v: new THREE.Vector3(),
      s: new THREE.Vector3(),
      mint: new THREE.Color(),
      ember: new THREE.Color(),
      chrome: new THREE.Color(),
      c: new THREE.Color(),
    }),
    [],
  )
  const proximity = useRef<number[]>(molecules.map(() => 0))

  useFrame((state, dtRaw) => {
    if (!pointer.visible || !atomsRef.current || !bondsRef.current) return
    const dt = Math.min(dtRaw, 1 / 30)
    const t = state.clock.elapsedTime
    const { energy, dark } = pointer

    blend(tmp.mint, 'mint', dark)
    blend(tmp.ember, 'ember', dark)
    blend(tmp.chrome, 'chrome', dark)

    if (group.current) {
      // Counter-parallax against the helix so the layers separate visibly.
      group.current.position.x = damp(group.current.position.x, -pointer.sx * 1.9, 1.6, dt)
      group.current.position.y = damp(
        group.current.position.y,
        -pointer.sy * 1.4 + pointer.scroll * 7,
        1.6,
        dt,
      )
    }

    const bondPos = bondsRef.current.geometry.getAttribute('position') as THREE.BufferAttribute
    const bondCol = bondsRef.current.geometry.getAttribute('color') as THREE.BufferAttribute
    const bp = bondPos.array as Float32Array
    const bc = bondCol.array as Float32Array

    let atomI = 0
    let bondI = 0

    for (let mi = 0; mi < molecules.length; mi++) {
      const mol = molecules[mi]

      mol.center.x += mol.drift.x * dt
      mol.center.y += mol.drift.y * dt
      // Wrap so the field never empties out.
      if (Math.abs(mol.center.x) > 18) mol.center.x *= -0.98
      if (Math.abs(mol.center.y) > 13) mol.center.y *= -0.98

      mol.rot.x += mol.spin.x * dt * (1 + energy)
      mol.rot.y += mol.spin.y * dt * (1 + energy)
      mol.rot.z += mol.spin.z * dt * 0.4

      // Cursor proximity in screen-ish space: near molecules wake up.
      const px = pointer.sx * 15
      const py = pointer.sy * 10
      const d = Math.hypot(mol.center.x - px, mol.center.y - py)
      const near = Math.max(0, 1 - d / 7)
      proximity.current[mi] = damp(proximity.current[mi], near, 4, dt)
      const wake = proximity.current[mi]

      tmp.q.setFromEuler(mol.rot)
      const breathe = 1 + Math.sin(t * 0.9 + mi) * 0.05 + wake * 0.22

      for (let ai = 0; ai < mol.atoms.length; ai++) {
        tmp.v.copy(mol.atoms[ai]).applyQuaternion(tmp.q).multiplyScalar(breathe).add(mol.center)
        const r = (0.085 + mol.radius * 0.1) * (1 + wake * 0.4)
        tmp.s.setScalar(r)
        tmp.m.compose(tmp.v, tmp.q, tmp.s)
        atomsRef.current.setMatrixAt(atomI, tmp.m)
        mol.world[ai].copy(tmp.v) // cached for the bond pass below
        atomI++
      }

      tmp.c.copy(mol.pole ? tmp.ember : tmp.mint).lerp(tmp.chrome, 0.35 - wake * 0.35)
      const k = (0.16 + wake * 0.7 + energy * 0.35) * (0.24 + dark * 0.76)

      for (const [a, b] of mol.bonds) {
        mol.world[a].toArray(bp, bondI * 6)
        mol.world[b].toArray(bp, bondI * 6 + 3)
        for (let v = 0; v < 2; v++) {
          const o = bondI * 6 + v * 3
          bc[o] = tmp.c.r * k
          bc[o + 1] = tmp.c.g * k
          bc[o + 2] = tmp.c.b * k
        }
        bondI++
      }
    }

    atomsRef.current.instanceMatrix.needsUpdate = true
    bondPos.needsUpdate = true
    bondCol.needsUpdate = true

    const mat = atomsRef.current.material as THREE.MeshStandardMaterial
    mat.emissive.copy(tmp.mint)
    mat.emissiveIntensity = 0.28 + energy * 0.6
    mat.color.copy(tmp.chrome)
    mat.opacity = 0.2 + dark * 0.55
  })

  return (
    <group ref={group}>
      <instancedMesh ref={atomsRef} args={[undefined, undefined, totalAtoms]}>
        <sphereGeometry args={[1, tier === 'low' ? 6 : 12, tier === 'low' ? 6 : 12]} />
        <meshStandardMaterial transparent roughness={0.3} metalness={0.4} toneMapped={false} />
      </instancedMesh>
      <lineSegments ref={bondsRef} geometry={bondGeom}>
        <lineBasicMaterial
          vertexColors
          transparent
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </lineSegments>
    </group>
  )
}
