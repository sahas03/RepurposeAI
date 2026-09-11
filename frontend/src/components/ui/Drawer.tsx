import { AnimatePresence, motion } from 'framer-motion'
import type { ReactNode } from 'react'
import { useEffect } from 'react'
import { cx } from '@/lib/cx'
import { Hud } from './Hud'

const EASE = [0.22, 1, 0.36, 1] as const

/**
 * A right-hand detail surface. Used for both stage methodology and candidate
 * detail so the two feel like the same drawer being re-loaded, which keeps the
 * page from ever navigating away from the results the user is reading.
 */
export function Drawer({
  open,
  onClose,
  eyebrow,
  title,
  subtitle,
  children,
  width = 'wide',
}: {
  open: boolean
  onClose: () => void
  eyebrow: string
  title: ReactNode
  subtitle?: ReactNode
  children: ReactNode
  width?: 'wide' | 'normal'
}) {
  useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => e.key === 'Escape' && onClose()
    document.addEventListener('keydown', onKey)
    const prev = document.body.style.overflow
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = prev
    }
  }, [open, onClose])

  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-[160]" role="dialog" aria-modal="true">
          <motion.button
            aria-label="Close detail"
            onClick={onClose}
            className="absolute inset-0 backdrop-blur-md"
            style={{ background: 'rgb(var(--veil) / 0.6)' }}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.35 }}
          />

          <motion.div
            className={cx(
              'absolute inset-y-0 right-0 flex w-full flex-col',
              width === 'wide' ? 'sm:max-w-[720px]' : 'sm:max-w-[520px]',
            )}
            initial={{ x: '100%' }}
            animate={{ x: 0 }}
            exit={{ x: '100%' }}
            transition={{ duration: 0.55, ease: EASE }}
          >
            <div className="glass flex h-full flex-col border-l border-line/16 shadow-lift">
              <header className="relative shrink-0 border-b border-line/12 px-6 py-6 sm:px-8">
                {/* scan line across the header, so the panel reads as live */}
                <span className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-mint/60 to-transparent" />
                <div className="flex items-start justify-between gap-4">
                  <div className="min-w-0">
                    <Hud className="mb-2.5 block text-mint">{eyebrow}</Hud>
                    <h3 className="font-display text-[24px] font-semibold leading-tight tracking-[-0.03em] text-ink sm:text-[28px]">
                      {title}
                    </h3>
                    {subtitle && <div className="mt-2.5">{subtitle}</div>}
                  </div>
                  <button
                    onClick={onClose}
                    data-cursor="button"
                    aria-label="Close"
                    className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-line/16 text-dim transition-colors hover:border-ember/45 hover:text-ember"
                  >
                    <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
                      <path
                        d="M1 1l12 12M13 1L1 13"
                        stroke="currentColor"
                        strokeWidth="1.4"
                        strokeLinecap="round"
                      />
                    </svg>
                  </button>
                </div>
              </header>

              <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-6 py-7 sm:px-8">
                {children}
              </div>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  )
}
