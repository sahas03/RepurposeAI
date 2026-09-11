import { useEffect } from 'react'
import { Nav } from '@/components/chrome/Nav'
import { ControlDock } from '@/components/chrome/ControlDock'
import { CustomCursor } from '@/components/chrome/CustomCursor'
import { Hero } from '@/components/sections/Hero'
import { DiscoverySequence } from '@/components/sections/DiscoverySequence'
import { PipelineSection } from '@/components/pipeline/PipelineSection'
import { SignatureSection } from '@/components/sections/SignatureSection'
import { LibrarySection } from '@/components/sections/LibrarySection'
import { ReversalSection } from '@/components/sections/ReversalSection'
import { SafetySection } from '@/components/sections/SafetySection'
import { CandidatesSection } from '@/components/candidates/CandidatesSection'
import { ExplainSection } from '@/components/sections/ExplainSection'
import { ValidationSection } from '@/components/sections/ValidationSection'
import { Footer } from '@/components/sections/Footer'
import { BioUniverse } from '@/three/BioUniverse'
import { attachPointerListeners } from '@/store/pointer'
import { useApp } from '@/store/useApp'

export default function App() {
  const preload = useApp((s) => s.preload)

  useEffect(() => attachPointerListeners(), [])
  // Parse the CSVs up front so the data views are populated before any run.
  useEffect(() => void preload(), [preload])

  return (
    <>
      <BioUniverse />
      <CustomCursor />
      <Nav />
      <main id="top" className="relative z-10">
        <Hero />
        <PipelineSection />
        <SignatureSection />
        <LibrarySection />
        <ReversalSection />
        <SafetySection />
        <CandidatesSection />
        <ExplainSection />
        <ValidationSection />
        <Footer />
      </main>
      <ControlDock />
      <DiscoverySequence />
    </>
  )
}
