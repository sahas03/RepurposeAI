import { motion, useMotionValueEvent, useScroll } from 'framer-motion'
import { useEffect, useState } from 'react'
import { cx } from '@/lib/cx'
import { Hud } from '@/components/ui/Hud'
import { useApp } from '@/store/useApp'
import { SystemStatus } from './SystemStatus'
import { ThemeToggle } from './ThemeToggle'
import { Wordmark } from './Wordmark'

const LINKS = [
  { id: 'discover', label: 'Discover' },
  { id: 'pipeline', label: 'Pipeline' },
  { id: 'signature', label: 'Signature' },
  { id: 'candidates', label: 'Candidates' },
  { id: 'explain', label: 'Explainability' },
  { id: 'validation', label: 'Validation' },
]

/**
 * Floating instrument bar. It contracts and gains opacity as the page scrolls
 * so it stops competing with the content, and the active link is tracked with
 * an IntersectionObserver rather than scroll math.
 */
export function Nav() {
  const { scrollY } = useScroll()
  const [compact, setCompact] = useState(false)
  const [active, setActive] = useState('discover')
  const disease = useApp((s) => s.settings.diseaseName)

  useMotionValueEvent(scrollY, 'change', (y) => setCompact(y > 90))

  useEffect(() => {
    const sections = LINKS.map((l) => document.getElementById(l.id)).filter(
      (el): el is HTMLElement => !!el,
    )
    const io = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((e) => e.isIntersecting)
          .sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0]
        if (visible) setActive(visible.target.id)
      },
      { rootMargin: '-45% 0px -45% 0px', threshold: [0, 0.25, 0.5, 1] },
    )
    sections.forEach((s) => io.observe(s))
    return () => io.disconnect()
  }, [])

  return (
    <motion.header
      className="fixed inset-x-0 top-0 z-[100] flex justify-center px-4 pt-4"
      animate={{ paddingTop: compact ? 8 : 16 }}
      transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
    >
      <motion.nav
        className={cx(
          'glass bevel relative flex w-full max-w-[1400px] items-center gap-3 rounded-2xl px-3',
          'transition-[height,background-color] duration-500 ease-expo',
        )}
        animate={{
          height: compact ? 54 : 66,
          backgroundColor: compact
            ? 'rgb(var(--glass) / calc(var(--glass-a) + 0.24))'
            : 'rgb(var(--glass) / calc(var(--glass-a) - 0.06))',
        }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
      >
        <a
          href="#top"
          data-cursor="button"
          className="flex shrink-0 items-center gap-2.5 pl-1 pr-2"
          aria-label="RepurposeAI, back to top"
        >
          <Wordmark compact={compact} />
        </a>

        <span className="hidden h-6 w-px bg-line/15 xl:block" />

        <ul className="hidden min-w-0 flex-1 items-center gap-0.5 xl:flex">
          {LINKS.map((l) => (
            <li key={l.id}>
              <a
                href={`#${l.id}`}
                data-cursor="button"
                className={cx(
                  'relative block rounded-md px-3 py-2 font-display text-[11.5px] font-medium uppercase tracking-wide2 transition-colors duration-300',
                  active === l.id ? 'text-mint' : 'text-dim hover:text-ink',
                )}
              >
                {l.label}
                {active === l.id && (
                  <motion.span
                    layoutId="nav-active"
                    className="absolute inset-x-2 -bottom-0.5 h-px bg-mint"
                    transition={{ type: 'spring', stiffness: 420, damping: 34 }}
                  />
                )}
              </a>
            </li>
          ))}
        </ul>

        <div className="ml-auto flex shrink-0 items-center gap-2.5 pr-1">
          <div className="hidden items-center gap-2 rounded-full border border-line/14 px-3 py-1.5 2xl:flex">
            <Hud>Target</Hud>
            <span className="font-display text-[11.5px] font-medium capitalize text-ink">
              {disease}
            </span>
          </div>
          <SystemStatus />
          <ThemeToggle />
        </div>
      </motion.nav>
    </motion.header>
  )
}
