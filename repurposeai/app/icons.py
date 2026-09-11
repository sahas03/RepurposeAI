"""
icons.py
A small, coherent inline-SVG icon set (thin-line, consistent stroke width)
replacing the mixed emoji used earlier. Every icon uses stroke="currentColor"
(fills for tiny accent dots only) so it recolors for free with CSS `color`
-- no separate light/dark asset needed. Deliberately a leaf module: no
imports from styles.py/graphics.py, so those can import this without risk
of a circular import.

Covers the six pipeline-stage concepts (disease signature, drug library,
reversal scoring, safety/novelty, explainability, validation) plus a couple
of directly-reused variants. Secondary decorative emoji elsewhere in the
app (pills, minor badges) were left as-is -- a deliberate scope boundary,
not an oversight; see the dashboard.py summary for what got converted.
"""

from __future__ import annotations

import math

_SW = 1.75  # shared stroke width -> reads as one icon family


def _svg(inner: str, size: int = 20, view: int = 24) -> str:
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {view} {view}" '
        f'fill="none" xmlns="http://www.w3.org/2000/svg" class="rpa-icon" '
        f'style="vertical-align:-0.15em;">{inner}</svg>'
    )


def _dna_path(width: float = 24, height: float = 24, turns: float = 1.6, steps: int = 26):
    amp = width * 0.22
    cx = width / 2
    a, b = [], []
    for i in range(steps + 1):
        t = i / steps
        y = t * height
        angle = t * turns * 2 * math.pi
        a.append((cx + amp * math.sin(angle), y))
        b.append((cx + amp * math.sin(angle + math.pi), y))
    pa = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in a)
    pb = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in b)
    rungs = "".join(
        f'<line x1="{a[i][0]:.1f}" y1="{a[i][1]:.1f}" x2="{b[i][0]:.1f}" y2="{b[i][1]:.1f}" stroke-width="1.1"/>'
        for i in range(2, steps - 1, 6)
    )
    return f'<path d="{pa}" stroke="currentColor" stroke-width="{_SW}" stroke-linecap="round"/>' \
           f'<path d="{pb}" stroke="currentColor" stroke-width="{_SW}" stroke-linecap="round"/>' \
           f'<g stroke="currentColor" opacity="0.75">{rungs}</g>'


_ICONS = {
    "dna": lambda: _dna_path(),
    "pill": lambda: (
        f'<g transform="rotate(45 12 12)">'
        f'<rect x="2.5" y="9" width="19" height="6" rx="3" stroke="currentColor" stroke-width="{_SW}"/>'
        f'<line x1="12" y1="9" x2="12" y2="15" stroke="currentColor" stroke-width="{_SW}"/>'
        f"</g>"
    ),
    "cycle": lambda: (
        f'<path d="M4.5 12a7.5 7.5 0 0 1 13.2-4.8M17.7 3.8v4.6h-4.6" stroke="currentColor" '
        f'stroke-width="{_SW}" stroke-linecap="round" stroke-linejoin="round"/>'
        f'<path d="M19.5 12a7.5 7.5 0 0 1-13.2 4.8M6.3 20.2v-4.6h4.6" stroke="currentColor" '
        f'stroke-width="{_SW}" stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "shield-check": lambda: (
        f'<path d="M12 2.5 L19.5 5.3 V11 C19.5 16 16 19.8 12 21.5 C8 19.8 4.5 16 4.5 11 V5.3 Z" '
        f'stroke="currentColor" stroke-width="{_SW}" stroke-linejoin="round"/>'
        f'<path d="M8.3 12 L10.8 14.6 L15.8 9.2" stroke="currentColor" stroke-width="{_SW}" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "search-network": lambda: (
        f'<circle cx="10" cy="10" r="7" stroke="currentColor" stroke-width="{_SW}"/>'
        f'<line x1="15.2" y1="15.2" x2="21" y2="21" stroke="currentColor" stroke-width="{_SW}" stroke-linecap="round"/>'
        f'<line x1="7" y1="8.5" x2="12" y2="7" stroke="currentColor" stroke-width="1"/>'
        f'<line x1="7" y1="8.5" x2="9.3" y2="13" stroke="currentColor" stroke-width="1"/>'
        f'<line x1="12" y1="7" x2="9.3" y2="13" stroke="currentColor" stroke-width="1"/>'
        f'<circle cx="7" cy="8.5" r="1.1" fill="currentColor" stroke="none"/>'
        f'<circle cx="12" cy="7" r="1.1" fill="currentColor" stroke="none"/>'
        f'<circle cx="9.3" cy="13" r="1.1" fill="currentColor" stroke="none"/>'
    ),
    "flask-check": lambda: (
        f'<circle cx="12" cy="12" r="9" stroke="currentColor" stroke-width="{_SW}"/>'
        f'<path d="M7.5 12.3 L10.4 15.3 L16.5 8.3" stroke="currentColor" stroke-width="{_SW}" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
    ),
    "asterisk": lambda: (
        f'<g stroke="currentColor" stroke-width="{_SW}" stroke-linecap="round">'
        f'<line x1="12" y1="4" x2="12" y2="20"/>'
        f'<line x1="5.5" y1="7.5" x2="18.5" y2="16.5"/>'
        f'<line x1="18.5" y1="7.5" x2="5.5" y2="16.5"/>'
        f"</g>"
    ),
}


def icon(name: str, size: int = 20, color: str | None = None, extra_style: str = "") -> str:
    """Render a named icon as an inline <svg> string. `color` overrides
    currentColor via an inline style (pass a CSS var() or hex)."""
    builder = _ICONS.get(name)
    if builder is None:
        raise KeyError(f"Unknown icon '{name}'. Available: {sorted(_ICONS)}")
    svg = _svg(builder(), size=size)
    if color or extra_style:
        style_bits = []
        if color:
            style_bits.append(f"color:{color};")
        if extra_style:
            style_bits.append(extra_style)
        svg = svg.replace('style="vertical-align:-0.15em;"', f'style="vertical-align:-0.15em;{"".join(style_bits)}"')
    return svg
