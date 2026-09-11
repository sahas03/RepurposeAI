import { useFrame } from '@react-three/fiber'
import { useMemo, useRef } from 'react'
import * as THREE from 'three'
import { damp, pointer } from '@/store/pointer'
import { blend, getGlowTexture, mulberry32 } from './palette'

/**
 * A sparse graph of nodes on a shell, wired to their nearest neighbours, with
 * pulses that travel along the edges.
 *
 * It is deliberately abstract: it stands for connectivity, not for any named
 * gene or pathway. Real pathway relationships are shown in the reasoning graph
 * inside the Explainability section, where they are derived from data.
 */
export function GeneNetwork({ tier }: { tier: 'high' | 'medium' | 'low' }) {
  const nodeCount = tier === 'high' ? 46 : tier === 'medium' ? 30 : 16

  const group = useRef<THREE.Group>(null)
  const nodesRef = useRef<THREE.Points>(null)
  const edgesRef = useRef<THREE.LineSegments>(null)
  const pulsesRef = useRef<THREE.Points>(null)

  const graph = useMemo(() => {
    const rand = mulberry32(9091)
    const nodes: THREE.Vector3[] = []
    for (let i = 0; i < nodeCount; i++) {
      // Fibonacci-ish shell placement gives even coverage without clumping.
      const y = 1 - (i / (nodeCount - 1)) * 2
      const r = Math.sqrt(Math.max(0, 1 - y * y))
      const theta = i * 2.399963
      const jitter = 0.85 + rand() * 0.3
      nodes.push(
        new THREE.Vector3(Math.cos(theta) * r, y * 0.72, Math.sin(theta) * r)
          .multiplyScalar(9.5 * jitter)
          .add(new THREE.Vector3(0, 0, -14)),
      )
    }

    // Connect each node to its two nearest neighbours. Cheap, and the result
    // is a connected mesh rather than a hairball.
    const edges: [number, number][] = []
    const seen = new Set<string>()
    for (let i = 0; i < nodes.length; i++) {
      const order = nodes
        .map((n, j) => ({ j, d: n.distanceTo(nodes[i]) }))
        .filter((x) => x.j !== i)
        .sort((a, b) => a.d - b.d)
        .slice(0, 2)
      for (const { j } of order) {
        const key = i < j ? `${i}:${j}` : `${j}:${i}`
        if (seen.has(key)) continue
        seen.add(key)
        edges.push([i, j])
      }
    }

    const nodePos = new Float32Array(nodes.length * 3)
    nodes.forEach((n, i) => n.toArray(nodePos, i * 3))
    const nodeGeom = new THREE.BufferGeometry()
    nodeGeom.setAttribute('position', new THREE.BufferAttribute(nodePos, 3))

    const edgePos = new Float32Array(edges.length * 6)
    edges.forEach(([a, b], i) => {
      nodes[a].toArray(edgePos, i * 6)
      nodes[b].toArray(edgePos, i * 6 + 3)
    })
    const edgeGeom = new THREE.BufferGeometry()
    edgeGeom.setAttribute('position', new THREE.BufferAttribute(edgePos, 3))
    edgeGeom.setAttribute('color', new THREE.BufferAttribute(new Float32Array(edges.length * 6), 3))

    // One pulse per edge, each starting at a different point along it.
    const pulseGeom = new THREE.BufferGeometry()
    pulseGeom.setAttribute(
      'position',
      new THREE.BufferAttribute(new Float32Array(edges.length * 3), 3),
    )
    const pulseT = new Float32Array(edges.length)
    const pulseSpeed = new Float32Array(edges.length)
    for (let i = 0; i < edges.length; i++) {
      pulseT[i] = rand()
      pulseSpeed[i] = 0.07 + rand() * 0.16
    }

    return { nodes, edges, nodeGeom, edgeGeom, pulseGeom, pulseT, pulseSpeed }
  }, [nodeCount])

  const col = useMemo(() => ({ mint: new THREE.Color(), iris: new THREE.Color() }), [])

  useFrame((_, dtRaw) => {
    if (!pointer.visible || !group.current) return
    const dt = Math.min(dtRaw, 1 / 30)
    const { energy, dark } = pointer
    blend(col.mint, 'mint', dark)
    blend(col.iris, 'iris', dark)

    group.current.rotation.y += dt * (0.018 + energy * 0.05)
    group.current.rotation.x = damp(group.current.rotation.x, pointer.sy * 0.08, 1.4, dt)
    group.current.position.x = damp(group.current.position.x, -12 - pointer.sx * 1.2, 1.4, dt)
    group.current.position.y = damp(group.current.position.y, 1 + pointer.scroll * 10, 1.4, dt)

    if (edgesRef.current) {
      const c = edgesRef.current.geometry.getAttribute('color') as THREE.BufferAttribute
      const arr = c.array as Float32Array
      const k = (0.1 + energy * 0.45) * (0.16 + dark * 0.84)
      for (let i = 0; i < graph.edges.length; i++) {
        for (let v = 0; v < 2; v++) {
          const o = i * 6 + v * 3
          arr[o] = col.mint.r * k
          arr[o + 1] = col.mint.g * k
          arr[o + 2] = col.mint.b * k
        }
      }
      c.needsUpdate = true
    }

    if (pulsesRef.current) {
      const p = pulsesRef.current.geometry.getAttribute('position') as THREE.BufferAttribute
      const arr = p.array as Float32Array
      const boost = 0.4 + energy * 2.4
      for (let i = 0; i < graph.edges.length; i++) {
        graph.pulseT[i] = (graph.pulseT[i] + graph.pulseSpeed[i] * boost * dt) % 1
        const [a, b] = graph.edges[i]
        const na = graph.nodes[a]
        const nb = graph.nodes[b]
        const t = graph.pulseT[i]
        arr[i * 3] = na.x + (nb.x - na.x) * t
        arr[i * 3 + 1] = na.y + (nb.y - na.y) * t
        arr[i * 3 + 2] = na.z + (nb.z - na.z) * t
      }
      p.needsUpdate = true
      const mat = pulsesRef.current.material as THREE.PointsMaterial
      mat.color.copy(col.iris)
      mat.opacity = (0.18 + energy * 0.6) * (0.3 + dark * 0.7)
      mat.size = 0.22 + energy * 0.2
    }

    if (nodesRef.current) {
      const mat = nodesRef.current.material as THREE.PointsMaterial
      mat.color.copy(col.mint)
      mat.opacity = (0.3 + energy * 0.4) * (0.22 + dark * 0.78)
    }
  })

  return (
    <group ref={group} position={[-12, 1, 0]}>
      <lineSegments ref={edgesRef} geometry={graph.edgeGeom}>
        <lineBasicMaterial
          vertexColors
          transparent
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </lineSegments>
      <points ref={nodesRef} geometry={graph.nodeGeom}>
        <pointsMaterial
          map={getGlowTexture()}
          size={0.42}
          transparent
          sizeAttenuation
          blending={THREE.AdditiveBlending}
          depthWrite={false}
          toneMapped={false}
        />
      </points>
      <points ref={pulsesRef} geometry={graph.pulseGeom}>
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
  )
}
