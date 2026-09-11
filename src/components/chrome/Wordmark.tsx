import { cx } from '@/lib/cx'

/**
 * The mark is two strands crossing inside an aperture: a helix read as a
 * reversal. It is drawn rather than imported so it can inherit the live theme
 * colours and animate its base pairs without shipping an asset.
 */
export function Glyph({ size = 28, animate = true }: { size?: number; animate?: boolean }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      aria-hidden="true"
      className="shrink-0 overflow-visible"
    >
      <rect
        x="1"
        y="1"
        width="30"
        height="30"
        rx="9"
        stroke="rgb(var(--c-line) / 0.28)"
        strokeWidth="1"
      />
      {/* the two strands, mirrored */}
      <path
        d="M11 4C11 10 21 10 21 16C21 22 11 22 11 28"
        stroke="rgb(var(--c-mint))"
        strokeWidth="1.7"
        strokeLinecap="round"
      />
      <path
        d="M21 4C21 10 11 10 11 16C11 22 21 22 21 28"
        stroke="rgb(var(--c-ember))"
        strokeWidth="1.7"
        strokeLinecap="round"
        opacity="0.82"
      />
      {/* base pairs, with a travelling highlight */}
      {[9, 16, 23].map((y, i) => (
        <line
          key={y}
          x1="11"
          y1={y}
          x2="21"
          y2={y}
          stroke="rgb(var(--c-mint))"
          strokeWidth="1.1"
          strokeLinecap="round"
          opacity="0.5"
        >
          {animate && (
            <animate
              attributeName="opacity"
              values="0.18;0.95;0.18"
              dur="3.4s"
              begin={`${i * 1.13}s`}
              repeatCount="indefinite"
            />
          )}
        </line>
      ))}
    </svg>
  )
}

export function Wordmark({ compact = false }: { compact?: boolean }) {
  return (
    <span className="flex items-center gap-2.5">
      <Glyph size={compact ? 24 : 27} />
      <span
        className={cx(
          'font-display font-semibold leading-none tracking-[-0.035em] transition-all duration-500 ease-expo',
          compact ? 'text-[15px]' : 'text-[17px]',
        )}
      >
        <span className="text-ink">Repurpose</span>
        <span className="text-mint">AI</span>
      </span>
    </span>
  )
}
