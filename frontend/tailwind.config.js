/** @type {import('tailwindcss').Config} */
export default {
  darkMode: ['class', '[data-theme="dark"]'],
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // Semantic surface / text tokens resolve through CSS vars so the
        // dark <-> light transition can be animated in one place.
        base: 'rgb(var(--c-base) / <alpha-value>)',
        surface: 'rgb(var(--c-surface) / <alpha-value>)',
        raised: 'rgb(var(--c-raised) / <alpha-value>)',
        line: 'rgb(var(--c-line) / <alpha-value>)',
        ink: 'rgb(var(--c-ink) / <alpha-value>)',
        dim: 'rgb(var(--c-dim) / <alpha-value>)',
        faint: 'rgb(var(--c-faint) / <alpha-value>)',
        // The two poles of the science: disease signal vs corrective signal.
        ember: 'rgb(var(--c-ember) / <alpha-value>)',
        mint: 'rgb(var(--c-mint) / <alpha-value>)',
        iris: 'rgb(var(--c-iris) / <alpha-value>)',
        signal: 'rgb(var(--c-signal) / <alpha-value>)',
        amber: 'rgb(var(--c-amber) / <alpha-value>)',
      },
      fontFamily: {
        display: ['"Space Grotesk Variable"', '"Space Grotesk"', 'system-ui', 'sans-serif'],
        sans: ['"Inter Variable"', 'Inter', 'system-ui', 'sans-serif'],
        mono: ['"JetBrains Mono Variable"', '"JetBrains Mono"', 'ui-monospace', 'monospace'],
      },
      letterSpacing: { hud: '0.22em', wide2: '0.14em' },
      borderRadius: { xl2: '1.25rem' },
      transitionTimingFunction: {
        expo: 'cubic-bezier(0.22, 1, 0.36, 1)',
        smooth: 'cubic-bezier(0.65, 0, 0.35, 1)',
      },
      boxShadow: {
        panel: '0 1px 0 0 rgb(var(--c-hi) / 0.07) inset, 0 24px 60px -24px rgb(var(--c-shadow) / 0.55)',
        lift: '0 1px 0 0 rgb(var(--c-hi) / 0.10) inset, 0 40px 90px -30px rgb(var(--c-shadow) / 0.7)',
      },
      keyframes: {
        'hud-blink': { '0%,100%': { opacity: '1' }, '50%': { opacity: '0.25' } },
        'energy-sweep': { '0%': { transform: 'translateX(-120%)' }, '100%': { transform: 'translateX(220%)' } },
        'slow-spin': { to: { transform: 'rotate(360deg)' } },
        float: { '0%,100%': { transform: 'translateY(0)' }, '50%': { transform: 'translateY(-6px)' } },
        'scan-y': { '0%': { transform: 'translateY(-100%)' }, '100%': { transform: 'translateY(600%)' } },
        'pulse-ring': {
          '0%': { transform: 'scale(0.75)', opacity: '0.65' },
          '100%': { transform: 'scale(2.1)', opacity: '0' },
        },
      },
      animation: {
        'hud-blink': 'hud-blink 2.4s ease-in-out infinite',
        'energy-sweep': 'energy-sweep 1.1s cubic-bezier(0.22,1,0.36,1)',
        'slow-spin': 'slow-spin 28s linear infinite',
        float: 'float 7s ease-in-out infinite',
        'scan-y': 'scan-y 3.6s linear infinite',
        'pulse-ring': 'pulse-ring 2.6s cubic-bezier(0.22,1,0.36,1) infinite',
      },
    },
  },
  plugins: [],
}
