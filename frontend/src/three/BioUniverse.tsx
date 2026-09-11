import { Canvas, useFrame, useThree } from '@react-three/fiber'
import { Suspense, useEffect, useMemo, useRef, useState } from 'react'
import * as THREE from 'three'
import { damp, detectTier, pointer } from '@/store/pointer'
import { GridFloor, Haze, ParticleField } from './Ambient'
import { DNAHelix } from './DNAHelix'
import { GeneNetwork } from './GeneNetwork'
import { MoleculeField } from './MoleculeField'
import { blend } from './palette'

/**
 * BioUniverse
 * One fixed, full-viewport canvas living behind the entire application.
 *
 * Every layer inside reads its motion from the shared `pointer` bus rather
 * than from React props, so the scene stays pointer-, scroll- and
 * state-reactive without ever re-rendering the React tree.
 */

/** Eases the shared smoothed values once per frame, before any layer reads them. */
function Rig() {
  const { camera, gl, scene } = useThree()
  const fog = useMemo(() => new THREE.FogExp2('#04090b', 0.021), [])
  const bg = useMemo(() => new THREE.Color(), [])

  useEffect(() => {
    scene.fog = fog
    gl.setClearAlpha(0)
    return () => {
      scene.fog = null
    }
  }, [scene, fog, gl])

  useFrame((_, dtRaw) => {
    const dt = Math.min(dtRaw, 1 / 30)
    pointer.sx = damp(pointer.sx, pointer.x, 3.2, dt)
    pointer.sy = damp(pointer.sy, pointer.y, 3.2, dt)
    pointer.energy = damp(pointer.energy, pointer.energyTarget, 2.4, dt)
    pointer.dark = damp(pointer.dark, pointer.darkTarget, 3.4, dt)

    // Fog carries most of the environment change between the two themes.
    blend(bg, 'bg', pointer.dark)
    fog.color.copy(bg)
    fog.density = 0.021 - pointer.dark * 0.004

    // A slow camera drift keeps the composition from ever being fully static.
    camera.position.x = damp(camera.position.x, pointer.sx * 0.85, 1.4, dt)
    camera.position.y = damp(camera.position.y, pointer.sy * 0.6, 1.4, dt)
    camera.lookAt(0, 0, -10)
  })

  return null
}

function Lights() {
  const key = useRef<THREE.PointLight>(null)
  const fill = useRef<THREE.PointLight>(null)
  const amb = useRef<THREE.AmbientLight>(null)
  const c = useMemo(() => ({ mint: new THREE.Color(), ember: new THREE.Color() }), [])

  useFrame(() => {
    blend(c.mint, 'mint', pointer.dark)
    blend(c.ember, 'ember', pointer.dark)
    if (key.current) {
      key.current.color.copy(c.mint)
      key.current.intensity = 30 + pointer.energy * 90
      key.current.position.x = 6 + pointer.sx * 4
      key.current.position.y = 4 + pointer.sy * 3
    }
    if (fill.current) {
      fill.current.color.copy(c.ember)
      fill.current.intensity = 12 + pointer.energy * 34
    }
    if (amb.current) amb.current.intensity = 0.35 + (1 - pointer.dark) * 1.5
  })

  return (
    <>
      <ambientLight ref={amb} />
      <pointLight ref={key} position={[6, 4, 4]} distance={70} decay={1.4} />
      <pointLight ref={fill} position={[-9, -5, -6]} distance={60} decay={1.5} />
    </>
  )
}

export function BioUniverse() {
  const [tier, setTier] = useState<'high' | 'medium' | 'low'>('medium')
  const [enabled, setEnabled] = useState(true)
  const shell = useRef<HTMLDivElement>(null)

  /**
   * Once the reader is into the content, the environment steps back. This is
   * an opacity write on the wrapper rather than anything inside the scene, so
   * it costs nothing and it dims every layer consistently. Pipeline energy
   * pulls some of the presence back: during a run the universe is meant to be
   * visibly working behind the results.
   */
  useEffect(() => {
    let raf = 0
    let current = 1
    const tick = () => {
      const target = Math.max(0.3, 1 - pointer.scroll * 4.5) + pointer.energy * 0.22
      current += (Math.min(1, target) - current) * 0.09
      if (shell.current) shell.current.style.opacity = current.toFixed(3)
      raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [])

  useEffect(() => {
    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    pointer.reducedMotion = reduced
    setTier(detectTier())

    // Respect the OS motion setting by dropping to a still, but still lit,
    // composition rather than removing the environment entirely.
    const onResize = () => setTier(detectTier())
    window.addEventListener('resize', onResize)
    return () => window.removeEventListener('resize', onResize)
  }, [])

  useEffect(() => {
    const onLost = (e: Event) => {
      e.preventDefault()
      setEnabled(false)
    }
    window.addEventListener('webglcontextlost', onLost)
    return () => window.removeEventListener('webglcontextlost', onLost)
  }, [])

  if (!enabled) return <StaticFallback />

  return (
    <div
      ref={shell}
      className="pointer-events-none fixed inset-0 z-0"
      aria-hidden="true"
      data-rpa="bio-universe"
    >
      <Canvas
        gl={{
          antialias: tier !== 'low',
          alpha: true,
          powerPreference: 'high-performance',
          stencil: false,
          depth: true,
        }}
        dpr={tier === 'high' ? [1, 1.75] : [1, 1.25]}
        camera={{ position: [0, 0, 14], fov: 52, near: 0.1, far: 220 }}
        onCreated={({ gl }) => {
          gl.toneMapping = THREE.ACESFilmicToneMapping
          gl.toneMappingExposure = 1.05
        }}
      >
        <Rig />
        <Lights />
        <Suspense fallback={null}>
          <GridFloor />
          <ParticleField tier={tier} />
          <Haze />
          <GeneNetwork tier={tier} />
          <MoleculeField tier={tier} />
          <DNAHelix tier={tier} />
        </Suspense>
      </Canvas>
      <Vignette />
    </div>
  )
}

/** CSS-only depth cue over the canvas. Free, and it frames the composition. */
function Vignette() {
  return (
    <div
      className="absolute inset-0"
      style={{
        background:
          'radial-gradient(ellipse 90% 70% at 50% 40%, transparent 40%, rgb(var(--veil) / 0.55) 100%)',
      }}
    />
  )
}

/** Shown if WebGL is unavailable or the context is lost mid-session. */
function StaticFallback() {
  return (
    <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden" aria-hidden="true">
      <div
        className="absolute -right-40 top-0 h-[120vh] w-[80vw] opacity-40"
        style={{
          background:
            'radial-gradient(circle at 60% 30%, rgb(var(--c-mint) / 0.18), transparent 55%), radial-gradient(circle at 20% 70%, rgb(var(--c-iris) / 0.12), transparent 55%)',
        }}
      />
    </div>
  )
}
