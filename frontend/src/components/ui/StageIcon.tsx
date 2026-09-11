import type { StageId } from '@/engine/run'

/**
 * One hand-drawn glyph per stage. Line-only, 1.3px, on a 24-unit grid so they
 * sit consistently next to mono type. Drawn rather than pulled from an icon
 * set because each one has to say something specific about its stage.
 */
export function StageIcon({ id, size = 22 }: { id: StageId; size?: number }) {
  const common = {
    width: size,
    height: size,
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    strokeWidth: 1.3,
    strokeLinecap: 'round' as const,
    strokeLinejoin: 'round' as const,
    'aria-hidden': true,
  }

  switch (id) {
    // A differential-expression trace: bars above and below a baseline.
    case 'signature':
      return (
        <svg {...common}>
          <path d="M2 12h20" opacity="0.4" />
          <path d="M5 12V6M8.5 12v-3M12 12V4M15.5 12v8M19 12v-5" />
        </svg>
      )
    // A compound library: repeated ring units.
    case 'library':
      return (
        <svg {...common}>
          <path d="M7 4.5l2.8 1.6v3.3L7 11 4.2 9.4V6.1z" />
          <path d="M17 4.5l2.8 1.6v3.3L17 11l-2.8-1.6V6.1z" />
          <path d="M12 13l2.8 1.6v3.3L12 19.5l-2.8-1.6v-3.3z" />
          <path d="M9.8 9.4L12 13M14.2 9.4L12 13" opacity="0.5" />
        </svg>
      )
    // Two signals mirroring each other about an axis.
    case 'reversal':
      return (
        <svg {...common}>
          <path d="M2.5 9c2.6 0 3.4-5 6-5s3.4 5 6 5 3.4-3 3.4-3" />
          <path d="M2.5 15c2.6 0 3.4 5 6 5s3.4-5 6-5 3.4 3 3.4 3" opacity="0.55" />
          <path d="M2 12h20" strokeDasharray="2 2.5" opacity="0.35" />
        </svg>
      )
    // A shield under a scan line.
    case 'safety':
      return (
        <svg {...common}>
          <path d="M12 3l6.5 2.4v5.3c0 4-2.7 7.4-6.5 8.9-3.8-1.5-6.5-4.9-6.5-8.9V5.4z" />
          <path d="M4 12.5h16" strokeDasharray="1.5 2" />
          <path d="M9.6 11.8l1.8 1.9 3.2-3.6" />
        </svg>
      )
    // A reasoning tree: one cause branching into effects.
    case 'explain':
      return (
        <svg {...common}>
          <circle cx="4.5" cy="12" r="2.1" />
          <circle cx="19.5" cy="6" r="1.8" />
          <circle cx="19.5" cy="12" r="1.8" />
          <circle cx="19.5" cy="18" r="1.8" />
          <path d="M6.6 12h4.4M11 12c0-3.2 2.5-6 6.7-6M11 12h6.7M11 12c0 3.2 2.5 6 6.7 6" />
        </svg>
      )
    // A flask with a verified mark.
    case 'validation':
      return (
        <svg {...common}>
          <path d="M9 3h6M10.2 3v5.2L5.6 17a2.2 2.2 0 002 3.2h8.8a2.2 2.2 0 002-3.2l-4.6-8.8V3" />
          <path d="M6.8 14.5h10.4" opacity="0.45" />
          <path d="M9.7 16.9l1.7 1.8 3-3.4" />
        </svg>
      )
  }
}
