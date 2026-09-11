"""
graphics.py
Decorative + explainer SVG generators: the ambient background layer (DNA
helix + node-network motif, matching the pitch deck's molecular/network
style) and the mirror-image heatmap explainer graphic. Pure presentation,
theme-aware, no pipeline logic. Split out of styles.py because these are
generated (not static) SVG markup and benefit from their own module.

Performance note: every animation here is a CSS `transform` (rotateY,
translate) or `opacity` tween -- both are GPU-compositable and never
trigger layout/reflow, which is what keeps this cheap enough to run
continuously behind a live demo on modest hardware.
"""

from __future__ import annotations

import math
import random

import streamlit as st

from styles import PALETTES, _rgba

# ---------------------------------------------------------------------------
# Background layer: DNA helix + node-network motif
# ---------------------------------------------------------------------------
_rng = random.Random(42)
_NET_W, _NET_H = 1200, 700
_NODES = [
    (
        round(_rng.uniform(40, _NET_W - 40), 1),
        round(_rng.uniform(40, _NET_H - 40), 1),
        round(_rng.uniform(2.2, 4.6), 1),
    )
    for _ in range(16)
]


def _node_dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _build_edges():
    edges = set()
    for i, n1 in enumerate(_NODES):
        nearest = sorted(
            ((j, _node_dist(n1, n2)) for j, n2 in enumerate(_NODES) if j != i),
            key=lambda pair: pair[1],
        )[:2]
        for j, _ in nearest:
            edges.add(tuple(sorted((i, j))))
    return sorted(edges)


_EDGES = _build_edges()


_helix_particle_rng = random.Random(11)


def _helix_svg(
    theme: str = "dark",
    visible_turns: int = 5,
    period_px: float = 170,
    width: float = 230,
    steps_per_turn: int = 25,
    rung_step: int = 5,
) -> str:
    """A vertically infinite-scrolling, glowing low-poly-wireframe DNA helix
    (faceted triangle mesh + glowing nodes + floating particles), styled
    after a reference the team liked -- a neon wireframe helix, not a flat
    line drawing. A few nodes pulse amber as "mutation marker" points.

    Two earlier designs both failed: (1) a flat SVG rotated with CSS
    rotateY() goes edge-on and effectively disappears every half-turn, and
    (2) *any* animation restarts from frame zero on every Streamlit rerun
    (a slider drag, a button click -- anything that reruns the script
    recreates this DOM node). Drawing exactly `visible_turns + 1` periods of
    the sine pattern and looping a translateY() by exactly one period's
    height sidesteps both: the strand never goes edge-on, and restarting a
    periodic loop from 0 is visually IDENTICAL to wherever it was --
    so a mid-scroll Streamlit rerun is imperceptible instead of a jump cut.
    A true 3D spin was tried and dropped for the same reliability reason.
    """
    p = PALETTES.get(theme, PALETTES["dark"])
    navy, teal = p["accents"]["navy"], p["accents"]["teal"]
    mutation_hex = p["accents"]["amber"]

    amplitude = width * 0.30
    cx = width / 2
    total_periods = visible_turns + 1  # one extra period as scroll buffer
    total_height = period_px * total_periods
    steps = steps_per_turn * total_periods

    pts_a, pts_b = [], []
    for i in range(steps + 1):
        y = (i / steps) * total_height
        angle = (y / period_px) * 2 * math.pi
        pts_a.append((cx + amplitude * math.sin(angle), y))
        pts_b.append((cx + amplitude * math.sin(angle + math.pi), y))

    path_a = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts_a)
    path_b = "M " + " L ".join(f"{x:.1f},{y:.1f}" for x, y in pts_b)

    # Low-poly "faceted" mesh: a straight rung at each sample point plus
    # diagonals to the next sample, turning the twisted ladder into a
    # triangle mesh (the wireframe look) instead of a plain line drawing.
    idxs = list(range(0, steps + 1, rung_step))
    mesh, nodes = [], []
    for k, i in enumerate(idxs):
        xa, y = pts_a[i]
        xb, _ = pts_b[i]
        is_mut = k % 5 == 2  # deterministic, evenly spaced "SNP" markers
        node_cls = "rpa-helix-node-mut" if is_mut else "rpa-helix-node"
        node_r = 3.4 if is_mut else 2.3
        nodes.append(f'<circle class="{node_cls}" cx="{xa:.1f}" cy="{y:.1f}" r="{node_r}"/>')
        nodes.append(f'<circle class="{node_cls}" cx="{xb:.1f}" cy="{y:.1f}" r="{node_r}"/>')
        rung_cls = ' class="rpa-helix-rung-mut"' if is_mut else ""
        mesh.append(f'<line x1="{xa:.1f}" y1="{y:.1f}" x2="{xb:.1f}" y2="{y:.1f}"{rung_cls}/>')
        if k < len(idxs) - 1:
            i1 = idxs[k + 1]
            xa1, y1 = pts_a[i1]
            xb1, _ = pts_b[i1]
            mesh.append(f'<line x1="{xa:.1f}" y1="{y:.1f}" x2="{xb1:.1f}" y2="{y1:.1f}"/>')
            mesh.append(f'<line x1="{xb:.1f}" y1="{y:.1f}" x2="{xa1:.1f}" y2="{y1:.1f}"/>')

    # A loose halo of soft, independently-twinkling particles drifting past
    # the helix (the reference's bokeh-dot effect), tiled with the same
    # period so they loop seamlessly along with everything else.
    particles = []
    for _ in range(18):
        px_ = _helix_particle_rng.uniform(-width * 0.35, width * 1.35)
        py_ = _helix_particle_rng.uniform(0, total_height)
        r = round(_helix_particle_rng.uniform(1.0, 2.6), 1)
        delay = round(_helix_particle_rng.uniform(0, 6), 2)
        dur = round(_helix_particle_rng.uniform(4, 7), 1)
        particles.append(
            f'<circle class="rpa-helix-particle" cx="{px_:.1f}" cy="{py_:.1f}" r="{r}" '
            f'style="animation-delay:{delay}s; animation-duration:{dur}s;"/>'
        )

    visible_height = period_px * visible_turns
    loop_seconds = round(period_px / 11, 1)  # slow, gentle flow
    return (
        f'<div class="rpa-helix-viewport" style="height:{visible_height:.0f}px;">'
        f'<svg class="rpa-helix-scroll" style="animation-duration:{loop_seconds}s; '
        f'--helix-loop-h:-{period_px:.0f}px;" viewBox="0 0 {width} {total_height:.0f}" '
        f'width="{width:.0f}" height="{total_height:.0f}" xmlns="http://www.w3.org/2000/svg">'
        f"<defs>"
        f'<linearGradient id="rpaHelixGrad" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0%" stop-color="{navy}"/><stop offset="100%" stop-color="{teal}"/>'
        f"</linearGradient>"
        f'<filter id="rpaHelixGlow" x="-60%" y="-60%" width="220%" height="220%">'
        f'<feGaussianBlur stdDeviation="2.4"/>'
        f"</filter>"
        f"</defs>"
        f'<g class="rpa-helix-particles">{"".join(particles)}</g>'
        f'<g class="rpa-helix-glow-layer"><path d="{path_a}"/><path d="{path_b}"/></g>'
        f'<g class="rpa-helix-mesh-layer">{"".join(mesh)}</g>'
        f'<path class="rpa-helix-strand" d="{path_a}"/>'
        f'<path class="rpa-helix-strand" d="{path_b}"/>'
        f'<g class="rpa-helix-nodes" style="--mutation-color:{mutation_hex};">{"".join(nodes)}</g>'
        f"</svg></div>"
    )


def _network_svg() -> str:
    lines = "".join(
        f'<line x1="{_NODES[i][0]}" y1="{_NODES[i][1]}" x2="{_NODES[j][0]}" y2="{_NODES[j][1]}"/>'
        for i, j in _EDGES
    )
    circles = "".join(
        f'<circle class="rpa-net-node" cx="{x}" cy="{y}" r="{r}" '
        f'style="animation-delay:{(idx * 0.37) % 5:.2f}s"/>'
        for idx, (x, y, r) in enumerate(_NODES)
    )
    return (
        f'<div class="rpa-net-wrap"><svg class="rpa-net-svg" viewBox="0 0 {_NET_W} {_NET_H}" '
        f'preserveAspectRatio="xMidYMid slice" xmlns="http://www.w3.org/2000/svg">'
        f'<g class="rpa-net-drift"><g class="rpa-net-lines">{lines}</g>{circles}</g>'
        f"</svg></div>"
    )


def render_background(theme: str = "dark") -> None:
    """Fixed, non-interactive ambient background: a bold navy->teal DNA
    helix (with a few pulsing mutation-marker rungs) flowing continuously,
    plus a drifting, twinkling node-network graphic. Sits behind all content."""
    html = f'<div class="rpa-bg-layer">{_helix_svg(theme)}{_network_svg()}</div>'
    st.markdown(html, unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Mirror-image heatmap explainer: disease signature (red, up) vs.
# drug-reversed signature (blue, down) -- "a match in reverse."
# ---------------------------------------------------------------------------
_HEAT_COLS, _HEAT_ROWS = 12, 3
_heat_rng = random.Random(7)
_HEAT_PATTERN = [round(_heat_rng.uniform(0.18, 1.0), 2) for _ in range(_HEAT_COLS * _HEAT_ROWS)]


def _heat_grid(pattern, base_rgb, cell=26, gap=3, x0=0, y0=0):
    cells = []
    for row in range(_HEAT_ROWS):
        for col in range(_HEAT_COLS):
            v = pattern[row * _HEAT_COLS + col]
            x = x0 + col * (cell + gap)
            y = y0 + row * (cell + gap)
            r, g, b = base_rgb
            cells.append(
                f'<rect x="{x}" y="{y}" width="{cell}" height="{cell}" rx="4" '
                f'fill="rgba({r},{g},{b},{v:.2f})"/>'
            )
    return "".join(cells)


def render_heatmap_explainer(theme: str = "dark") -> None:
    """Static explainer graphic: disease-up genes (red) mirrored by
    drug-down genes (blue) -- the core Connectivity Map intuition,
    at a glance, before any numbers appear."""
    p = PALETTES.get(theme, PALETTES["dark"])
    text_color = p["text_primary"]
    dim_color = p["text_dim"]
    panel = p["bg_panel"]
    border = p["border_soft"]

    grid_w = _HEAT_COLS * 29
    grid_h = _HEAT_ROWS * 29
    top_grid = _heat_grid(_HEAT_PATTERN, (220, 60, 70), x0=0, y0=0)
    mirrored = [round(1.15 - v, 2) for v in _HEAT_PATTERN]
    mirrored = [min(1.0, max(0.15, v)) for v in mirrored]
    bottom_grid = _heat_grid(mirrored, (56, 130, 220), x0=0, y0=0)

    svg_w = grid_w + 40
    svg_h = grid_h * 2 + 70

    html = f"""
    <div class="rpa-heatmap-card">
      <svg viewBox="0 0 {svg_w} {svg_h}" width="100%" height="{svg_h}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="Disease signature versus drug-reversed signature">
        <text x="4" y="14" fill="{dim_color}" font-family="JetBrains Mono, monospace" font-size="11" letter-spacing="0.06em">DISEASE SIGNATURE (GENES UP)</text>
        <g transform="translate(4, 22)">{top_grid}</g>
        <g transform="translate({svg_w/2 - 10}, {grid_h + 22})">
          <line x1="10" y1="0" x2="10" y2="26" stroke="{dim_color}" stroke-width="2"/>
          <polygon points="10,32 3,20 17,20" fill="{dim_color}"/>
        </g>
        <text x="4" y="{grid_h + 62}" fill="{dim_color}" font-family="JetBrains Mono, monospace" font-size="11" letter-spacing="0.06em">DRUG SIGNATURE (GENES DOWN)</text>
        <g transform="translate(4, {grid_h + 70})">{bottom_grid}</g>
      </svg>
      <div class="rpa-heatmap-caption">Disease signature vs. drug-reversed signature — a match in reverse.</div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
