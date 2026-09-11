"""
styles.py
Visual design system for the dashboard: fonts, a theme-aware navy/teal
design language (matching the team's pitch deck), the animated pipeline
step diagram (with live per-stage progress states), HTML-based stat cards,
and a custom HTML table renderer. Pure presentation -- no pipeline logic
lives here, safe to restyle without touching anything else in app/.

Theming approach: Streamlit's own light/dark switcher only takes effect on
the NEXT script rerun, which desyncs the page (native chrome flips
instantly, custom CSS lags a run behind). To keep a one-click toggle always
in sync, this app owns theming end-to-end instead of relying on Streamlit's
switch: one fixed base theme in .streamlit/config.toml, and every visible
pixel (including native widget chrome and candidate tables, which normally
use Streamlit's canvas-rendered dataframe grid) is redrawn from these
Python palettes on every rerun via inject_css(theme) + render_table().
"""

from __future__ import annotations

import html as _html

import pandas as pd
import streamlit as st

from icons import icon as _icon

# (icon name, label, description) -- accent color is computed per-step via
# navy->teal interpolation (see step_diagram_html), not a fixed class. Icon
# names key into icons.py's custom thin-line set (see icons.py: "dna" is
# reused for the double helix, "cycle" for reversal's mirror-match idea).
PIPELINE_STEPS = [
    ("dna", "Disease Signature", "RA vs. healthy DEGs"),
    ("pill", "Drug Library", "LINCS L1000 signatures"),
    ("cycle", "Reversal Scoring", "cosine / WTCS match"),
    ("shield-check", "Safety & Novelty", "Lipinski proxy + known-hit flag"),
    ("search-network", "Explainability", "gene + pathway rationale"),
    ("flask-check", "Validation", "recovers known RA drugs?"),
]

_ACCENT_NAMES = ("navy", "teal", "cyan", "purple", "pink", "amber", "green", "red")

# Brand accents = navy + teal/emerald (pitch deck palette). "cyan"/"purple"/
# "green" are kept as aliases pointing at the same two brand hexes so every
# existing call site (render_stats(accent="cyan"), badges, buttons, hero
# panel, divider) picks up the new palette without being individually
# rewired. "amber"/"red"/"pink" stay reserved for functional states
# (warning/error) and are never used as a primary brand accent.
PALETTES = {
    "dark": {
        "bg_void": "#05070d",
        "bg_void_2": "#060a14",
        "bg_panel": "#0b1120",
        "bg_panel_2": "#101a30",
        "bg_panel_glass": "rgba(13, 20, 38, 0.55)",
        "border_soft": "rgba(148, 163, 184, 0.16)",
        "border_strong": "rgba(148, 163, 184, 0.32)",
        "text_primary": "#e6edf7",
        "text_dim": "#8fa1bd",
        "grid_line": "rgba(148, 163, 184, 0.045)",
        "scrollbar_thumb": "#1e293b",
        "grad_end": "#ffffff",
        "accents": {
            "navy": "#0b5fa5",
            "teal": "#14b8a6",
            "cyan": "#14b8a6",
            "purple": "#0b5fa5",
            "green": "#14b8a6",
            "pink": "#f472b6",
            "amber": "#f59e0b",
            "red": "#ef4444",
        },
        "glow_alpha": 0.45,
        "bg_glow_alpha": 0.10,
        "tint_bg_alpha": 0.13,
        "tint_border_alpha": 0.38,
    },
    "light": {
        "bg_void": "#e8edf6",
        "bg_void_2": "#dfe6f2",
        "bg_panel": "#ffffff",
        "bg_panel_2": "#f4f7fc",
        "bg_panel_glass": "rgba(255, 255, 255, 0.68)",
        "border_soft": "rgba(15, 23, 42, 0.11)",
        "border_strong": "rgba(15, 23, 42, 0.24)",
        "text_primary": "#0b1324",
        "text_dim": "#4b5875",
        "grid_line": "rgba(15, 23, 42, 0.055)",
        "scrollbar_thumb": "#c7d2e0",
        "grad_end": "#0b1324",
        "accents": {
            "navy": "#0b5fa5",
            "teal": "#14b8a6",
            "cyan": "#14b8a6",
            "purple": "#0b5fa5",
            "green": "#14b8a6",
            "pink": "#be185d",
            "amber": "#f59e0b",
            "red": "#ef4444",
        },
        "glow_alpha": 0.16,
        "bg_glow_alpha": 0.07,
        "tint_bg_alpha": 0.10,
        "tint_border_alpha": 0.34,
    },
}


def _hex_to_rgb(hex_color: str) -> tuple:
    h = hex_color.lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def _rgba(hex_color: str, alpha: float) -> str:
    r, g, b = _hex_to_rgb(hex_color)
    return f"rgba({r}, {g}, {b}, {alpha})"


def interp_hex(c1: str, c2: str, t: float) -> str:
    r1, g1, b1 = _hex_to_rgb(c1)
    r2, g2, b2 = _hex_to_rgb(c2)
    r = round(r1 + (r2 - r1) * t)
    g = round(g1 + (g2 - g1) * t)
    b = round(b1 + (b2 - b1) * t)
    return f"#{r:02x}{g:02x}{b:02x}"


def _build_root_vars(theme: str) -> str:
    p = PALETTES.get(theme, PALETTES["dark"])
    lines = [
        f"--bg-void: {p['bg_void']};",
        f"--bg-void-2: {p['bg_void_2']};",
        f"--bg-panel: {p['bg_panel']};",
        f"--bg-panel-2: {p['bg_panel_2']};",
        f"--bg-panel-glass: {p['bg_panel_glass']};",
        f"--border-soft: {p['border_soft']};",
        f"--border-strong: {p['border_strong']};",
        f"--text-primary: {p['text_primary']};",
        f"--text-dim: {p['text_dim']};",
        f"--grid-line: {p['grid_line']};",
        f"--scrollbar-thumb: {p['scrollbar_thumb']};",
        f"--grad-end: {p['grad_end']};",
    ]
    accents = p["accents"]
    lines.append(f"--glow-cyan-bg: {_rgba(accents['teal'], p['bg_glow_alpha'])};")
    lines.append(f"--glow-purple-bg: {_rgba(accents['navy'], p['bg_glow_alpha'] * 1.1)};")
    for name in _ACCENT_NAMES:
        hexval = accents[name]
        lines.append(f"--{name}: {hexval};")
        lines.append(f"--{name}-glow: {_rgba(hexval, p['glow_alpha'])};")
        lines.append(f"--{name}-bg: {_rgba(hexval, p['tint_bg_alpha'])};")
        lines.append(f"--{name}-border: {_rgba(hexval, p['tint_border_alpha'])};")
    return "\n".join(lines)


_CSS_STATIC = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400;500;700&display=swap');

:root {
__ROOT_VARS__
    --font-display: 'Space Grotesk', 'Inter', sans-serif;
    --font-body: 'Inter', sans-serif;
    --font-mono: 'JetBrains Mono', 'Consolas', monospace;
}

/* ---------- base canvas ---------- */
.stApp {
    background:
        radial-gradient(ellipse 1200px 600px at 12% -10%, var(--glow-cyan-bg), transparent 60%),
        radial-gradient(ellipse 900px 500px at 100% 0%, var(--glow-purple-bg), transparent 55%),
        linear-gradient(180deg, var(--bg-void) 0%, var(--bg-void-2) 100%);
    background-attachment: fixed;
}
.stApp::before {
    content: "";
    position: fixed;
    inset: 0;
    pointer-events: none;
    background-image:
        linear-gradient(var(--grid-line) 1px, transparent 1px),
        linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
    background-size: 42px 42px;
    mask-image: radial-gradient(ellipse 80% 60% at 50% 0%, black 20%, transparent 75%);
    z-index: 0;
}
[data-testid="stAppViewContainer"] { position: relative; z-index: 1; }
[data-testid="stHeader"] { background: var(--bg-void) !important; position: relative; z-index: 2; }
[data-testid="stHeader"] svg { fill: var(--text-dim) !important; }
[data-testid="stSidebar"] { position: relative; z-index: 2; }
[data-testid="stMainBlockContainer"] { padding-top: 1.6rem; }

html, body, [class*="css"] { font-family: var(--font-body); font-size: 17px; color: var(--text-primary); }

/* ---------- typography ---------- */
h1, h2, h3 { font-family: var(--font-display) !important; letter-spacing: -0.01em; color: var(--text-primary) !important; }
h1 { font-size: 2.5rem !important; font-weight: 700 !important; }
h2 {
    font-size: 1.65rem !important; font-weight: 600 !important;
    display: flex; align-items: center; gap: 0.55rem;
    padding-bottom: 0.35rem;
    border-bottom: 1px solid var(--border-soft);
    margin-top: 0.4rem !important;
}
h3 { font-size: 1.25rem !important; font-weight: 600 !important; }
p, li, span, label { font-family: var(--font-body); }
[data-testid="stMarkdownContainer"] p { color: var(--text-primary); }
code, .rpa-mono { font-family: var(--font-mono) !important; }

[data-testid="stCaptionContainer"] {
    font-family: var(--font-mono) !important;
    color: var(--text-dim) !important;
    letter-spacing: 0.01em;
}

/* ---------- sidebar ---------- */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, var(--bg-panel-2) 0%, var(--bg-void) 100%);
    border-right: 1px solid var(--border-soft);
}
[data-testid="stSidebar"] h1, [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
    font-family: var(--font-display) !important;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p { color: var(--text-primary); }

/* ---------- buttons ---------- */
[data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"],
button[kind="primary"], button[kind="secondary"] {
    font-family: var(--font-display) !important;
    font-weight: 600 !important;
    border-radius: 10px !important;
    letter-spacing: 0.01em;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
}
button[kind="primary"] {
    background: linear-gradient(135deg, var(--navy), var(--teal)) !important;
    border: none !important;
    color: #ffffff !important;
    box-shadow: 0 0 22px var(--teal-glow);
}
button[kind="primary"]:hover { transform: translateY(-1px); box-shadow: 0 0 30px var(--teal-glow); }
button[kind="secondary"] {
    border: 1px solid var(--border-strong) !important;
    background: var(--bg-panel) !important;
    color: var(--text-primary) !important;
}

/* ---------- native widget chrome (select / slider / radio / checkbox / toggle) ---------- */
[data-baseweb="select"] > div, [data-baseweb="base-input"], [data-baseweb="input"] > div {
    background: var(--bg-panel) !important;
    border-color: var(--border-strong) !important;
    color: var(--text-primary) !important;
}
[data-baseweb="popover"] li, [data-baseweb="menu"] li { background: var(--bg-panel) !important; color: var(--text-primary) !important; }
[data-testid="stSlider"] [data-baseweb="slider"] > div:nth-child(2) { background: var(--border-strong) !important; }
[data-testid="stSlider"] [data-baseweb="slider"] > div:nth-child(3) { background: var(--teal) !important; }
[data-testid="stSlider"] [role="slider"] { background: var(--teal) !important; border-color: var(--teal) !important; }
[data-testid="stWidgetLabel"] p { color: var(--text-primary) !important; font-weight: 500; }
[data-testid="stRadio"] label, [data-testid="stCheckbox"] label { color: var(--text-primary) !important; }
[data-testid="stTickBar"] { display: none; }

/* toggle switch (theme switcher) */
[data-testid="stToggle"] [role="checkbox"][aria-checked="true"] { background: var(--teal) !important; border-color: var(--teal) !important; }
[data-testid="stToggle"] label p { color: var(--text-primary) !important; font-weight: 600; }

/* ---------- inputs ---------- */
[data-testid="stExpander"] {
    background: var(--bg-panel-glass);
    -webkit-backdrop-filter: blur(10px);
    backdrop-filter: blur(10px);
    border: 1px solid var(--border-soft) !important;
    border-radius: 12px !important;
    overflow: hidden;
}
[data-testid="stExpander"] summary { font-family: var(--font-display) !important; font-weight: 600; }
[data-testid="stExpander"] p { color: var(--text-primary); }

[data-testid="stAlert"] {
    border-radius: 12px !important;
    border: 1px solid var(--border-soft) !important;
    font-family: var(--font-body);
}

[data-testid="stDataFrame"] {
    border: 1px solid var(--border-soft) !important;
    border-radius: 12px !important;
    overflow: hidden;
}

hr, [data-testid="stDivider"] { border-color: var(--border-soft) !important; }

/* scrollbars */
::-webkit-scrollbar { width: 10px; height: 10px; }
::-webkit-scrollbar-track { background: var(--bg-void); }
::-webkit-scrollbar-thumb { background: var(--scrollbar-thumb); border-radius: 6px; }

/* ---------- ambient background: DNA helix + node network ---------- */
.rpa-bg-layer { position: fixed; inset: 0; z-index: 0; pointer-events: none; overflow: hidden; }
.rpa-helix-viewport {
    position: absolute; top: -2%; left: 50%; transform: translateX(-50%); width: 230px;
    overflow: hidden; opacity: 0.26;
}
.rpa-helix-scroll {
    display: block;
    animation-name: rpaHelixLoop;
    animation-timing-function: linear;
    animation-iteration-count: infinite;
}
/* Looping a periodic sine pattern by exactly one period is visually
   seamless -- so even if Streamlit recreates this element on a rerun
   (any widget interaction does), restarting the loop from 0 never
   produces a visible jump, unlike a one-shot rotation would. */
@keyframes rpaHelixLoop { from { transform: translateY(0); } to { transform: translateY(var(--helix-loop-h, -140px)); } }

/* Glowing low-poly wireframe: a soft blurred duplicate of the strands sits
   behind the crisp core strand + faceted mesh, giving the neon-outline look
   without needing a raster/3D asset. */
.rpa-helix-glow-layer path {
    fill: none; stroke: var(--teal); stroke-width: 7; opacity: 0.55;
    filter: url(#rpaHelixGlow);
}
.rpa-helix-strand {
    fill: none; stroke-width: 2; stroke-linecap: round;
    stroke: url(#rpaHelixGrad);
    filter: drop-shadow(0 0 3px var(--teal));
}
.rpa-helix-mesh-layer line { stroke: var(--teal); stroke-width: 0.8; opacity: 0.4; }
.rpa-helix-rung-mut { stroke: var(--amber) !important; stroke-width: 1.3; opacity: 0.95; }
.rpa-helix-node {
    fill: var(--teal); filter: drop-shadow(0 0 3px var(--teal));
    animation: rpaTwinkle 4s ease-in-out infinite;
}
.rpa-helix-node-mut {
    fill: var(--mutation-color); filter: drop-shadow(0 0 5px var(--mutation-color));
    animation: rpaHelixAtomPulse 1.8s ease-in-out infinite;
}
.rpa-helix-particle {
    fill: var(--teal); opacity: 0.5; filter: drop-shadow(0 0 2px var(--teal));
    animation: rpaTwinkle 5s ease-in-out infinite;
}
@keyframes rpaHelixAtomPulse {
    0%, 100% { opacity: 0.55; filter: drop-shadow(0 0 1px var(--mutation-color)); }
    50% { opacity: 1; filter: drop-shadow(0 0 6px var(--mutation-color)); }
}

.rpa-net-wrap { position: absolute; inset: 0; opacity: 0.10; }
.rpa-net-svg { width: 100%; height: 100%; }
.rpa-net-lines line { stroke: var(--navy); stroke-width: 1; }
.rpa-net-node { fill: var(--teal); filter: drop-shadow(0 0 3px var(--teal)); animation: rpaTwinkle 5s ease-in-out infinite; transform-origin: center; }
.rpa-net-drift { animation: rpaDrift 46s ease-in-out infinite; }
@keyframes rpaDrift {
    0%, 100% { transform: translate(0, 0); }
    25% { transform: translate(10px, -8px); }
    50% { transform: translate(-6px, 6px); }
    75% { transform: translate(6px, 10px); }
}
@keyframes rpaTwinkle { 0%, 100% { opacity: 0.35; } 50% { opacity: 0.95; } }

/* ---------- heatmap explainer card ---------- */
.rpa-heatmap-card {
    background: var(--bg-panel-glass);
    -webkit-backdrop-filter: blur(10px);
    backdrop-filter: blur(10px);
    border: 1px solid var(--border-soft);
    border-radius: 14px;
    padding: 14px 16px 10px 16px;
    margin: 0.3rem 0 1.4rem 0;
}
.rpa-heatmap-caption {
    font-family: var(--font-mono); font-size: 0.78rem; color: var(--text-dim);
    text-align: center; margin-top: 6px; letter-spacing: 0.01em;
}

/* ---------- step diagram ---------- */
.rpa-step-row { display: flex; flex-wrap: wrap; align-items: stretch; gap: 0.5rem; margin: 0.6rem 0 1.7rem 0; position: relative; }
.rpa-step {
    flex: 1 1 150px; position: relative; overflow: hidden;
    background: linear-gradient(160deg, rgba(255,255,255,0.06), rgba(255,255,255,0.01)), var(--bg-panel-glass);
    -webkit-backdrop-filter: blur(8px);
    backdrop-filter: blur(8px);
    border: 1px solid var(--border-soft);
    border-radius: 14px;
    padding: 16px 12px 14px 12px;
    text-align: center;
    box-shadow: 0 4px 18px rgba(0,0,0,0.16);
    transition: transform 0.2s ease, border-color 0.2s ease, box-shadow 0.2s ease, opacity 0.2s ease, filter 0.2s ease;
}
.rpa-step:hover { transform: translateY(-4px) scale(1.02); box-shadow: 0 10px 28px rgba(0,0,0,0.22), 0 0 26px var(--step-glow); border-color: var(--step-accent); }
.rpa-step .icon-wrap {
    width: 42px; height: 42px; margin: 0 auto 8px auto; border-radius: 10px; position: relative; z-index: 1;
    display: flex; align-items: center; justify-content: center; font-size: 1.35rem;
    background: linear-gradient(135deg, var(--step-accent), transparent 140%);
    box-shadow: 0 0 16px var(--step-glow);
}
.rpa-mutation-badge {
    position: absolute; top: -8px; right: -6px; width: 19px; height: 19px; border-radius: 50%;
    background: var(--mutation-color); display: flex; align-items: center; justify-content: center;
    box-shadow: 0 0 8px var(--mutation-color), 0 1px 3px rgba(0,0,0,0.35);
    border: 2px solid var(--bg-void); z-index: 2;
    animation: rpaMutationPulse 1.8s ease-in-out infinite;
}
@keyframes rpaMutationPulse {
    0%, 100% { box-shadow: 0 0 6px var(--mutation-color), 0 1px 3px rgba(0,0,0,0.35); }
    50% { box-shadow: 0 0 14px var(--mutation-color), 0 1px 3px rgba(0,0,0,0.35); }
}
.rpa-icon { display: inline-block; }
.rpa-step .label { font-family: var(--font-display); font-weight: 700; font-size: 1.0rem; display: block; color: var(--text-primary); position: relative; z-index: 1; }
.rpa-step .desc { font-family: var(--font-mono); font-weight: 400; font-size: 0.72rem; color: var(--text-dim); display: block; margin-top: 4px; position: relative; z-index: 1; }

.rpa-step[data-state="pending"] { opacity: 0.5; filter: saturate(0.6); }
.rpa-step[data-state="active"] {
    border-color: var(--step-accent);
    box-shadow: 0 0 0 1px var(--step-accent), 0 0 22px var(--step-glow);
    animation: rpaStepPulse 1.1s ease-in-out infinite;
}
.rpa-step[data-state="done"] { border-color: var(--step-accent); }
.rpa-step[data-state="error"] {
    border-color: var(--red); box-shadow: 0 0 0 1px var(--red), 0 0 20px var(--red-glow);
}
@keyframes rpaStepPulse {
    0%, 100% { box-shadow: 0 0 0 1px var(--step-accent), 0 0 16px var(--step-glow); }
    50% { box-shadow: 0 0 0 1px var(--step-accent), 0 0 32px var(--step-glow); }
}

.rpa-connector { flex: 0 0 26px; align-self: center; position: relative; height: 2px; }
.rpa-connector::before {
    content: ""; position: absolute; left: 0; right: 0; top: 50%; height: 2px; transform: translateY(-50%);
    background-image: repeating-linear-gradient(90deg, var(--teal) 0 6px, transparent 6px 12px);
    background-size: 24px 2px;
    animation: rpaFlow 1s linear infinite;
    opacity: 0.75;
}
@keyframes rpaFlow { from { background-position: 0 0; } to { background-position: 24px 0; } }

/* ---------- stat cards (replaces bare st.metric for headline numbers) ---------- */
.rpa-stat-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.6rem; margin: 0.5rem 0 1.2rem 0; }
.rpa-stat {
    background: linear-gradient(160deg, rgba(255,255,255,0.06), rgba(255,255,255,0.01)), var(--bg-panel-glass);
    -webkit-backdrop-filter: blur(8px);
    backdrop-filter: blur(8px);
    border: 1px solid var(--border-soft);
    border-left: 3px solid var(--stat-accent);
    border-radius: 12px;
    padding: 14px 16px;
    box-shadow: 0 4px 16px rgba(0,0,0,0.14);
}
.rpa-stat .stat-label {
    font-family: var(--font-mono); font-size: 0.72rem; letter-spacing: 0.04em;
    text-transform: uppercase; color: var(--text-dim); display: flex; align-items: center; gap: 6px;
}
.rpa-stat .stat-value {
    font-family: var(--font-display); font-weight: 700; font-size: 2.1rem; line-height: 1.25;
    background: linear-gradient(135deg, var(--stat-accent), var(--grad-end) 180%);
    -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
    margin-top: 2px;
}
.rpa-stat.cyan, .rpa-stat.teal { --stat-accent: var(--teal); --stat-glow: var(--teal-glow); }
.rpa-stat.purple, .rpa-stat.navy { --stat-accent: var(--navy); --stat-glow: var(--navy-glow); }
.rpa-stat.pink { --stat-accent: var(--pink); --stat-glow: var(--pink-glow); }
.rpa-stat.amber { --stat-accent: var(--amber); --stat-glow: var(--amber-glow); }
.rpa-stat.green { --stat-accent: var(--teal); --stat-glow: var(--teal-glow); }
.rpa-stat.red { --stat-accent: var(--red); --stat-glow: var(--red-glow); }

/* ---------- known / novel badges + hero panel ---------- */
.rpa-badge-known, .rpa-badge-novel {
    font-family: var(--font-mono); font-weight: 700; font-size: 0.78rem;
    padding: 4px 12px; border-radius: 999px; display: inline-flex; align-items: center; gap: 6px;
    letter-spacing: 0.02em; margin-bottom: 6px;
}
.rpa-badge-known { background: var(--teal-bg); color: var(--teal); border: 1px solid var(--teal-border); }
.rpa-badge-novel { background: var(--navy-bg); color: var(--navy); border: 1px solid var(--navy-border); }

.rpa-pill {
    font-family: var(--font-mono); font-size: 0.82rem; font-weight: 600;
    background: var(--teal-bg); color: var(--teal);
    border: 1px solid var(--teal-border);
    padding: 3px 11px; border-radius: 999px; display: inline-block; margin: 2px 4px 2px 0;
}

.rpa-hero {
    background: linear-gradient(135deg, var(--teal-bg), var(--navy-bg));
    border: 1px solid var(--teal-border);
    border-radius: 16px;
    padding: 4px;
    margin-bottom: 0.6rem;
}

.rpa-divider-glow {
    height: 1px; margin: 1.6rem 0;
    background: linear-gradient(90deg, transparent, var(--teal), transparent);
    opacity: 0.5;
}

/* ---------- purposeful motion: reveal-on-render ---------- */
@keyframes rpaFadeSlideIn { from { opacity: 0; transform: translateY(14px); } to { opacity: 1; transform: translateY(0); } }
.rpa-reveal { animation: rpaFadeSlideIn 320ms ease-out both; }

/* ---------- custom data table (theme-synced replacement for st.dataframe) ---------- */
.rpa-table-wrap {
    border: 1px solid var(--border-soft);
    border-radius: 12px;
    overflow: auto;
    max-height: 440px;
    background: var(--bg-panel);
    margin-bottom: 0.7rem;
}
.rpa-table { width: 100%; border-collapse: collapse; font-size: 0.92rem; }
.rpa-table thead th {
    position: sticky; top: 0;
    background: var(--bg-panel-2);
    color: var(--text-dim);
    font-family: var(--font-mono);
    font-size: 0.7rem;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    text-align: left;
    padding: 10px 14px;
    border-bottom: 1px solid var(--border-soft);
    white-space: nowrap;
}
.rpa-table tbody td {
    padding: 8px 14px;
    border-bottom: 1px solid var(--border-soft);
    color: var(--text-primary);
    white-space: nowrap;
}
.rpa-table tbody tr:hover td { background: var(--teal-bg); }
.rpa-table tbody tr:last-child td { border-bottom: none; }
.rpa-table td.num { font-family: var(--font-mono); text-align: right; }
.rpa-table td.center { text-align: center; }
.rpa-table-empty {
    font-family: var(--font-mono); font-size: 0.85rem; color: var(--text-dim);
    padding: 14px; text-align: center; border: 1px dashed var(--border-strong); border-radius: 12px;
}

/* ---------- comparison strip ---------- */
.rpa-compare-card {
    background: var(--bg-panel-glass);
    -webkit-backdrop-filter: blur(8px);
    backdrop-filter: blur(8px);
    border: 1px solid var(--border-soft);
    border-radius: 14px;
    padding: 14px 16px;
    height: 100%;
}
.rpa-compare-card.edge { border-color: var(--teal-border); box-shadow: 0 0 18px var(--teal-glow); }
.rpa-compare-title { font-family: var(--font-display); font-weight: 700; font-size: 1.0rem; margin-bottom: 8px; display: block; }
.rpa-compare-card ul { margin: 0; padding-left: 1.1rem; }
.rpa-compare-card li { font-size: 0.88rem; color: var(--text-primary); margin-bottom: 6px; line-height: 1.4; }
.rpa-compare-card li b { color: var(--teal); }
</style>
"""


def inject_css(theme: str = "dark") -> None:
    css = _CSS_STATIC.replace("__ROOT_VARS__", _build_root_vars(theme))
    st.markdown(css, unsafe_allow_html=True)


def step_diagram_html(theme: str = "dark", active: int | None = None, done: set | None = None, error: int | None = None) -> str:
    """Renders the 6-step pipeline diagram. Pass `active`/`done`/`error` (0-based
    step indices) to reflect live progress during an actual pipeline run --
    each card's state is driven by real stage execution, not a fake timer."""
    p = PALETTES.get(theme, PALETTES["dark"])
    navy, teal = p["accents"]["navy"], p["accents"]["teal"]
    glow_alpha = p["glow_alpha"]
    done = done or set()
    n = len(PIPELINE_STEPS)

    mutation_hex = p["accents"]["amber"]

    cells = []
    for i, (icon_name, label, desc) in enumerate(PIPELINE_STEPS):
        t = i / (n - 1)
        accent_hex = interp_hex(navy, teal, t)
        glow = _rgba(accent_hex, glow_alpha)

        if error == i:
            state = "error"
        elif active == i:
            state = "active"
        elif i in done:
            state = "done"
        elif active is not None and i > active:
            state = "pending"
        else:
            state = "idle"

        # Disease Signature = where an abnormal expression pattern is the whole
        # premise -- a small pulsing mutation-marker glyph nods at that without
        # being a literal/medical graphic.
        mutation_badge = (
            f'<span class="rpa-mutation-badge" style="--mutation-color:{mutation_hex};" '
            f'title="Disease signature = abnormal gene expression">{_icon("asterisk", size=11, color="#ffffff")}</span>'
            if i == 0
            else ""
        )

        cells.append(
            f'<div class="rpa-step" data-state="{state}" style="--step-accent:{accent_hex}; --step-glow:{glow};">'
            f'{mutation_badge}'
            f'<div class="icon-wrap">{_icon(icon_name, size=22, color="#ffffff")}</div>'
            f'<span class="label">{label}</span>'
            f'<span class="desc">{desc}</span></div>'
        )
        if i < n - 1:
            cells.append('<div class="rpa-connector"></div>')

    return f'<div class="rpa-step-row">{"".join(cells)}</div>'


def render_step_diagram(theme: str = "dark") -> None:
    st.markdown(step_diagram_html(theme), unsafe_allow_html=True)


def render_section_header(icon_name: str, text: str, level: str = "h2") -> None:
    """Raw <h1>/<h2> with one of icons.py's custom SVGs in place of an emoji --
    reuses the existing h1/h2 CSS (tag selectors, not testid-scoped) so it
    matches st.title()/st.header() exactly."""
    size = 28 if level == "h1" else 22
    st.markdown(f"<{level}>{_icon(icon_name, size=size)} {text}</{level}>", unsafe_allow_html=True)


def render_stats(items: list[dict]) -> None:
    """items: [{label, value, icon, accent}] -- accent in navy/teal (brand) or amber/red (warning/error)."""
    cells = []
    for item in items:
        icon = item.get("icon", "")
        accent = item.get("accent", "teal")
        cells.append(
            f'<div class="rpa-stat {accent}">'
            f'<div class="stat-label">{icon} {item["label"]}</div>'
            f'<div class="stat-value">{item["value"]}</div>'
            f'</div>'
        )
    st.markdown(f'<div class="rpa-stat-row rpa-reveal">{"".join(cells)}</div>', unsafe_allow_html=True)


def render_pills(values: list[str]) -> None:
    pills = "".join(f'<span class="rpa-pill">{_html.escape(str(v))}</span>' for v in values)
    st.markdown(f'<div class="rpa-reveal">{pills}</div>', unsafe_allow_html=True)


def glow_divider() -> None:
    st.markdown('<div class="rpa-divider-glow"></div>', unsafe_allow_html=True)


def render_table(df: pd.DataFrame, rename: dict | None = None, max_height: int = 420) -> None:
    """Theme-synced HTML table -- used instead of st.dataframe so the light/dark
    toggle reaches the candidate tables too (st.dataframe's grid is canvas-drawn
    and doesn't follow arbitrary page CSS)."""
    if df is None or df.empty:
        st.markdown('<div class="rpa-table-empty">No rows to show.</div>', unsafe_allow_html=True)
        return

    display_df = df.rename(columns=rename) if rename else df
    cols = list(display_df.columns)
    header = "".join(f"<th>{_html.escape(str(c))}</th>" for c in cols)

    rows_html = []
    for _, row in display_df.iterrows():
        cells = []
        for c in cols:
            v = row[c]
            if isinstance(v, bool):
                cells.append(f'<td class="center">{"✓" if v else "—"}</td>')
            elif isinstance(v, float):
                cells.append(f'<td class="num">{v:.3f}</td>')
            elif isinstance(v, int):
                cells.append(f'<td class="num">{v}</td>')
            else:
                cells.append(f"<td>{_html.escape(str(v))}</td>")
        rows_html.append(f"<tr>{''.join(cells)}</tr>")

    table_html = (
        f'<div class="rpa-table-wrap rpa-reveal" style="max-height:{max_height}px;">'
        f'<table class="rpa-table"><thead><tr>{header}</tr></thead>'
        f'<tbody>{"".join(rows_html)}</tbody></table></div>'
    )
    st.markdown(table_html, unsafe_allow_html=True)


def render_compare_strip() -> None:
    """'Why this approach' comparison -- reuses the deck's framing verbatim
    (systematic / interpretable / patient-level / safety-first) for the
    RepurposeAI column."""
    cols = st.columns(3)
    cards = [
        (
            "Traditional Repurposing",
            False,
            [
                "Serendipity-driven — relies on chance clinical observations",
                "No systematic genome-wide screening",
                "Slow: years per candidate discovered",
            ],
        ),
        (
            "Generic ML Screens",
            False,
            [
                "Black-box predictions — hard to explain to clinicians or regulators",
                "Often disease-agnostic, not patient-signature-specific",
                "No built-in safety or validation step",
            ],
        ),
        (
            "RepurposeAI's Edge",
            True,
            [
                "<b>Systematic</b> — screens the full drug-signature library, not guesswork",
                "<b>Interpretable</b> — gene-level rationale for every candidate",
                "<b>Patient-level</b> — matches an actual disease expression signature",
                "<b>Safety-first</b> — druglikeness screening and known-drug validation built in",
            ],
        ),
    ]
    for col, (title, is_edge, bullets) in zip(cols, cards):
        with col:
            card_class = "rpa-compare-card edge" if is_edge else "rpa-compare-card"
            items = "".join(f"<li>{b}</li>" for b in bullets)
            st.markdown(
                f'<div class="{card_class}"><span class="rpa-compare-title">{title}</span>'
                f"<ul>{items}</ul></div>",
                unsafe_allow_html=True,
            )
