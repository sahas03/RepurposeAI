"""
dashboard.py
RepurposeAI Phase 5 demo -- CBIT Ideathon 5.0.

Narrative: disease signature -> drug library -> reversal scoring ->
safety/novelty filter -> explainability -> validation. Built to run today
on mock data and swap to real data without a rewrite (see DATA SOURCE in
the sidebar, which auto-detects data/processed/*.csv).

Run: streamlit run app/dashboard.py

Ownership note: this file and everything else under app/ is Phase 5.
Everything imported from src/ is called through run_stage() (app/pipeline.py)
with the *exact* current signatures documented in each src module -- if a
teammate changes one overnight, the call site below is the only thing that
needs fixing.
"""

from __future__ import annotations

import concurrent.futures as cf
import os
import sys
import time

import pandas as pd
import streamlit as st

APP_DIR = os.path.dirname(__file__)
SRC_DIR = os.path.join(APP_DIR, "..", "src")
SCRIPTS_DIR = os.path.join(APP_DIR, "..", "scripts")
# Real data lives in data/processed/. data/raw/ holds ONLY synthetic mock
# data, which scripts/generate_mock_data.py and tests/test_pipeline.py
# regenerate on every run -- never point real-data loading at it.
REAL_DATA_DIR = os.path.join(APP_DIR, "..", "data", "processed")
MOCK_DATA_DIR = os.path.join(APP_DIR, "..", "data", "raw")
sys.path.insert(0, SRC_DIR)
sys.path.insert(0, SCRIPTS_DIR)

from data_loader import (  # noqa: E402
    load_disease_signature,
    load_l1000_matrix,
    harmonize_genes,
    zscore_disease_signature,
)
from signature_matching import cosine_reversal_score, weighted_connectivity_score, rank_candidates  # noqa: E402
from interpretability import top_contributing_genes, pathway_enrichment  # noqa: E402
from filters import apply_safety_filter, apply_novelty_filter, combine_scores, RDKIT_AVAILABLE  # noqa: E402
from validate import check_recovery, format_validation_statement, KNOWN_VALIDATION_SETS  # noqa: E402
import generate_mock_data  # noqa: E402

from pipeline import run_stage, StageError  # noqa: E402
from fast_scoring import cosine_reversal_score_fast  # noqa: E402
from validation_helpers import has_real_validation_signal, synthetic_ground_truth_check  # noqa: E402
from styles import (  # noqa: E402
    inject_css,
    step_diagram_html,
    render_stats,
    render_pills,
    render_table,
    render_compare_strip,
    render_section_header,
    glow_divider,
)
from graphics import render_background, render_heatmap_explainer  # noqa: E402

DISEASE_PATH = os.path.join(REAL_DATA_DIR, "disease_signature.csv")
L1000_PATH = os.path.join(REAL_DATA_DIR, "l1000_matrix.csv")
SMILES_LOOKUP_PATH = os.path.join(REAL_DATA_DIR, "smiles_lookup.csv")
APPROVED_DRUGS_PATH = os.path.join(REAL_DATA_DIR, "approved_drugs.txt")

# Synthetic-only paths, used by the "Generate fresh mock/demo data" option.
MOCK_DISEASE_PATH = os.path.join(MOCK_DATA_DIR, "disease_signature.csv")
MOCK_L1000_PATH = os.path.join(MOCK_DATA_DIR, "l1000_matrix.csv")

st.set_page_config(page_title="RepurposeAI", page_icon="🧬", layout="wide")

if "dark_mode" not in st.session_state:
    st.session_state["dark_mode"] = True
active_theme = "dark" if st.session_state["dark_mode"] else "light"
inject_css(active_theme)


# --------------------------------------------------------------------------
# Cached, thin wrappers over src/ calls (file IO + scoring are the expensive
# steps worth memoizing between reruns of the same inputs).
# --------------------------------------------------------------------------
@st.cache_data(show_spinner=False)
def _cached_load_disease(path_or_file):
    return load_disease_signature(path_or_file)


@st.cache_data(show_spinner=False)
def _cached_load_l1000(path_or_file):
    return load_l1000_matrix(path_or_file)


@st.cache_data(show_spinner=False)
def _cached_harmonize(disease_df, l1000_df):
    return harmonize_genes(disease_df, l1000_df)


@st.cache_data(show_spinner=False)
def _cached_cosine(disease_vec, l1000_df):
    return cosine_reversal_score(disease_vec, l1000_df)


@st.cache_data(show_spinner=False)
def _cached_cosine_fast(disease_vec, l1000_df):
    return cosine_reversal_score_fast(disease_vec, l1000_df)


@st.cache_data(show_spinner=False)
def _cached_wtcs(disease_df, l1000_df):
    return weighted_connectivity_score(disease_df, l1000_df)


def _try_pathway_enrichment(gene_list, gene_sets="KEGG_2021_Human", timeout=6):
    """Best-effort Enrichr call. Never raises -- returns (df_or_None, note_or_None)."""
    if not gene_list:
        return None, "No reversed genes to analyze."
    with cf.ThreadPoolExecutor(max_workers=1) as ex:
        future = ex.submit(pathway_enrichment, gene_list, gene_sets)
        try:
            return future.result(timeout=timeout), None
        except cf.TimeoutError:
            return None, "Pathway enrichment timed out (no internet at the venue?) -- showing gene-level explanation only."
        except Exception as e:  # noqa: BLE001
            return None, f"Pathway enrichment unavailable ({type(e).__name__}) -- showing gene-level explanation only."


# --------------------------------------------------------------------------
# Header + orientation
# --------------------------------------------------------------------------
render_background(active_theme)

render_section_header("dna", "RepurposeAI", level="h1")
st.caption("AI-powered drug repurposing for Rheumatoid Arthritis — CBIT Ideathon 5.0")

diagram_slot = st.empty()
diagram_slot.markdown(step_diagram_html(active_theme), unsafe_allow_html=True)

render_heatmap_explainer(active_theme)

with st.expander("🔎 What's real vs. simplified in this demo (honest-answer cheat sheet)"):
    st.markdown(
        """
- **Reversal scoring** — cosine similarity is the default (fast, simple, easy to defend).
  A closer-to-original-CMap **Weighted Connectivity Score (WTCS)** is available as an
  optional alt method in the sidebar (Advanced settings) — not the default because it's
  slower and more sensitive to threshold choices.
- **Safety screening** — Lipinski's Rule of Five (via RDKit) is a **fast druglikeness
  proxy**, not full ADMET modeling. It also only applies to small molecules — biologics
  like adalimumab or etanercept don't have a SMILES structure, so they're excluded from
  that check rather than mis-scored.
- **Known vs. novel labeling** — sourced directly from `validate.KNOWN_VALIDATION_SETS`,
  a small hand-curated reference list, not a full DrugBank indication database.
- **Pathway enrichment** — a live Enrichr API call. If the venue wifi is down, it fails
  fast and the dashboard falls back to the gene-level explanation only (never a crash).
- **Fast scoring toggle** — an optional vectorized reimplementation of the team's cosine
  scoring, added in `app/fast_scoring.py` (not a change to `src/signature_matching.py`),
  used only for speed on large drug libraries. Same math, same output.
- **Data** — this run is using **{data_label}**, shown below once the pipeline runs.
        """.replace("{data_label}", "whatever data source you pick in the sidebar")
    )

# --------------------------------------------------------------------------
# Sidebar
# --------------------------------------------------------------------------
with st.sidebar:
    title_col, toggle_col = st.columns([3, 1.3])
    with title_col:
        st.header("Pipeline Input")
    with toggle_col:
        st.toggle("🌙 / ☀️", key="dark_mode", help="Switch between dark and light theme")

    disease_name = st.selectbox("Target disease", list(KNOWN_VALIDATION_SETS.keys()))

    data_on_disk = os.path.exists(DISEASE_PATH) and os.path.exists(L1000_PATH)
    source_options = []
    if data_on_disk:
        source_options.append("Auto-detected files in data/processed/")
    source_options += ["Upload my own CSVs", "Generate fresh mock/demo data"]
    data_source = st.radio("Data source", source_options, index=0)

    disease_file = l1000_file = None
    if data_source == "Upload my own CSVs":
        disease_file = st.file_uploader("Disease signature CSV", type="csv")
        l1000_file = st.file_uploader("L1000 drug matrix CSV", type="csv")

    display_top_n = st.slider("Candidates to display", 5, 50, 15)

    with st.expander("⚙️ Advanced settings"):
        scoring_method = st.radio(
            "Reversal scoring method",
            ["Cosine similarity (default)", "Weighted Connectivity Score (WTCS, experimental)"],
        )
        fast_mode = st.checkbox(
            "⚡ Fast vectorized cosine scoring",
            value=True,
            help="Matrix-multiply implementation instead of a per-drug loop -- "
            "same math, much faster on large drug libraries. See app/fast_scoring.py.",
        )
        validation_top_k = st.slider(
            "Validation top-K (drugs considered for recovery check)", 5, 50, 20
        )

    run_button = st.button("▶ Run pipeline", type="primary", use_container_width=True)

# --------------------------------------------------------------------------
# Run pipeline
# --------------------------------------------------------------------------
if run_button:
    st.session_state.pop("pipeline_error", None)
    st.session_state.pop("ranked", None)

    STEP_DWELL = 0.15  # floor so a cache-hit rerun is still perceptible, well under the 300ms motion budget

    def _advance(active_idx, done_indices):
        diagram_slot.markdown(step_diagram_html(active_theme, active=active_idx, done=done_indices), unsafe_allow_html=True)
        time.sleep(STEP_DWELL)

    current_idx = 0
    try:
        _advance(0, set())
        if data_source == "Upload my own CSVs":
            if disease_file is None or l1000_file is None:
                st.error("Please upload both the disease signature and L1000 matrix CSVs.")
                st.stop()
            disease_df = run_stage("Load disease signature", load_disease_signature, disease_file)
            current_idx = 1
            _advance(1, {0})
            l1000_df = run_stage("Load L1000 matrix", load_l1000_matrix, l1000_file)
            data_label = "uploaded CSVs"
        elif data_source == "Generate fresh mock/demo data":
            with st.spinner("Generating synthetic demo data..."):
                run_stage("Generate mock data", generate_mock_data.main)
            disease_df = run_stage("Load disease signature", _cached_load_disease, MOCK_DISEASE_PATH)
            current_idx = 1
            _advance(1, {0})
            l1000_df = run_stage("Load L1000 matrix", _cached_load_l1000, MOCK_L1000_PATH)
            data_label = "freshly generated synthetic demo data"
        else:
            disease_df = run_stage("Load disease signature", _cached_load_disease, DISEASE_PATH)
            current_idx = 1
            _advance(1, {0})
            l1000_df = run_stage("Load L1000 matrix", _cached_load_l1000, L1000_PATH)
            data_label = "data/processed/ files (auto-detected)"

        n_drugs_total = l1000_df.shape[1]

        disease_df, l1000_df = run_stage("Harmonize genes", _cached_harmonize, disease_df, l1000_df)
        disease_vec = run_stage("Z-score disease signature", zscore_disease_signature, disease_df)

        current_idx = 2
        _advance(2, {0, 1})
        pool_n = max(display_top_n, validation_top_k, 20)
        if scoring_method.startswith("Weighted"):
            scores = run_stage("Score candidates (WTCS)", _cached_wtcs, disease_df, l1000_df)
            method_label = "Weighted Connectivity Score (WTCS)"
        elif fast_mode:
            scores = run_stage("Score candidates (vectorized cosine)", _cached_cosine_fast, disease_vec, l1000_df)
            method_label = "Cosine similarity (vectorized fast path)"
        else:
            scores = run_stage("Score candidates (cosine)", _cached_cosine, disease_vec, l1000_df)
            method_label = "Cosine similarity"

        ranked = run_stage("Rank candidates", rank_candidates, scores, pool_n)

        current_idx = 3
        _advance(3, {0, 1, 2})
        known_drugs_for_disease = KNOWN_VALIDATION_SETS.get(disease_name.lower(), set())
        known_indications = {d: {disease_name} for d in known_drugs_for_disease}
        ranked = run_stage("Novelty filter", apply_novelty_filter, ranked, known_indications, disease_name)

        safety_available = os.path.exists(SMILES_LOOKUP_PATH) and RDKIT_AVAILABLE
        if safety_available:
            smiles_df = pd.read_csv(SMILES_LOOKUP_PATH)
            smiles_lookup = dict(zip(smiles_df["drug"], smiles_df["smiles"]))
            approved_set = None
            if os.path.exists(APPROVED_DRUGS_PATH):
                with open(APPROVED_DRUGS_PATH) as f:
                    approved_set = {line.strip() for line in f if line.strip()}
            ranked = run_stage("Safety filter", apply_safety_filter, ranked, smiles_lookup, approved_set)

        ranked = run_stage("Combine scores", combine_scores, ranked)

        # stages 4 (Explainability) and 5 (Validation) run lazily just below,
        # the instant their data dependency exists -- no fake dwell needed.
        diagram_slot.markdown(step_diagram_html(active_theme, done={0, 1, 2, 3, 4, 5}), unsafe_allow_html=True)

        st.session_state.update(
            dict(
                ranked=ranked,
                disease_vec=disease_vec,
                l1000_df=l1000_df,
                disease_name=disease_name,
                data_label=data_label,
                method_label=method_label,
                safety_available=safety_available,
                display_top_n=display_top_n,
                validation_top_k=validation_top_k,
                n_genes_matched=len(disease_df),
                n_drugs_total=n_drugs_total,
            )
        )
    except StageError as e:
        st.session_state["pipeline_error"] = e
        diagram_slot.markdown(
            step_diagram_html(active_theme, done=set(range(current_idx)), error=current_idx),
            unsafe_allow_html=True,
        )

# --------------------------------------------------------------------------
# Error state
# --------------------------------------------------------------------------
if st.session_state.get("pipeline_error"):
    e = st.session_state["pipeline_error"]
    st.error(f"⚠️ Pipeline broke at **{e.stage}** — {type(e.original).__name__}: {e.original}")
    with st.expander("Technical details (for whoever's driving the demo)"):
        st.code(e.traceback_str)

# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------
if "ranked" in st.session_state:
    ranked = st.session_state["ranked"]
    disease_vec = st.session_state["disease_vec"]
    l1000_df = st.session_state["l1000_df"]
    disease_name = st.session_state["disease_name"]
    display_top_n = st.session_state["display_top_n"]
    validation_top_k = st.session_state["validation_top_k"]

    st.caption(
        f"Data source: **{st.session_state['data_label']}** · "
        f"Scoring method: **{st.session_state['method_label']}**"
    )

    render_stats(
        [
            {"label": "Genes matched", "value": st.session_state["n_genes_matched"], "icon": "🧬", "accent": "teal"},
            {"label": "Drugs scored", "value": st.session_state["n_drugs_total"], "icon": "💊", "accent": "navy"},
            {"label": "Candidates shown", "value": min(display_top_n, len(ranked)), "icon": "📋", "accent": "teal"},
            {
                "label": "Safety screen",
                "value": "ACTIVE" if st.session_state["safety_available"] else "NOT LOADED",
                "icon": "🛡️",
                "accent": "green" if st.session_state["safety_available"] else "amber",
            },
        ]
    )

    glow_divider()

    # ---- Validation hero ---------------------------------------------
    render_section_header("flask-check", "Validation — does this method actually work?")
    known_drugs = KNOWN_VALIDATION_SETS.get(disease_name.lower().strip(), set())
    real_signal = has_real_validation_signal(l1000_df.columns, known_drugs)

    if real_signal:
        try:
            result = run_stage("Validation check", check_recovery, ranked, disease_name, top_k=validation_top_k)
            st.markdown('<div class="rpa-hero rpa-reveal">', unsafe_allow_html=True)
            render_stats(
                [
                    {"label": "Recovery rate", "value": f"{result['recovery_rate'] * 100:.0f}%", "icon": "🎯", "accent": "green"},
                    {
                        "label": "Known drugs recovered",
                        "value": f"{result['recovered_count']}/{result['reference_set_size']}",
                        "icon": "✅",
                        "accent": "cyan",
                    },
                    {"label": "Novel candidates found", "value": len(result["novel_candidates"]), "icon": "🆕", "accent": "purple"},
                ]
            )
            if result["recovered_drugs"]:
                render_pills([f"💊 {d}" for d in result["recovered_drugs"]])
            st.markdown("</div>", unsafe_allow_html=True)
            st.info(format_validation_statement(result))
            with st.expander("Why does recovering *known* drugs prove anything?"):
                st.write(
                    "If a method can blindly re-discover drugs that are already proven "
                    "effective for this disease — purely from gene-expression math, with "
                    "no prior knowledge of the drug baked in — that's direct evidence the "
                    "scoring is picking up a real biological signal, not noise. It's not a "
                    "'boring' result: it's the calibration check that makes the *novel* "
                    "candidates below credible."
                )
        except StageError as e:
            st.warning(f"Validation check failed at {e.stage}: {e.original}")
    else:
        synthetic = synthetic_ground_truth_check(ranked, l1000_df.columns, top_k=validation_top_k)
        if synthetic:
            st.warning(
                "Running on **synthetic demo data** — drug names here are placeholders, "
                "not real compounds, so the real known-drug check (baricitinib, adalimumab, "
                "...) correctly finds zero matches. Shown below instead is the *planted "
                "ground-truth* sanity check built into the mock data generator."
            )
            st.markdown('<div class="rpa-hero rpa-reveal">', unsafe_allow_html=True)
            render_stats(
                [
                    {
                        "label": "Planted reversal drugs recovered",
                        "value": f"{synthetic['recovered_count']}/{synthetic['planted_total']}",
                        "icon": "🎯",
                        "accent": "green",
                    },
                    {"label": "Recovery rate (synthetic)", "value": f"{synthetic['recovery_rate'] * 100:.0f}%", "icon": "📈", "accent": "cyan"},
                ]
            )
            if synthetic["recovered"]:
                render_pills([f"💊 {d}" for d in synthetic["recovered"]])
            st.markdown("</div>", unsafe_allow_html=True)
            if not synthetic["reinforcing_ranks"].empty:
                st.caption("Planted *reinforcing* (bad) drugs — these should rank near the bottom, not the top:")
                render_table(
                    synthetic["reinforcing_ranks"][["rank", "drug", "reversal_score"]],
                    rename={"rank": "Rank", "drug": "Drug", "reversal_score": "Score"},
                )
            st.info(
                "This proves the ranking math correctly separates true reversal signal from "
                "noise and from reinforcing signal. The real validation panel above (known RA "
                "drug recovery) activates automatically once real L1000 drug names are loaded."
            )
        else:
            st.info(
                f"No reference drugs for **{disease_name}** were found among the "
                f"{l1000_df.shape[1]} drugs in this dataset, and no planted synthetic ground "
                "truth was detected either. Validation will activate once known drug identities "
                "are present — see `KNOWN_VALIDATION_SETS` in `src/validate.py`."
            )

    glow_divider()

    # ---- Ranked candidates: known vs novel -----------------------------
    st.subheader("Ranked Candidates")
    sort_col = "final_rank" if "final_rank" in ranked.columns else "rank"
    display_table = ranked.sort_values(sort_col).head(display_top_n).copy()

    # keep a single unified rank column (drop whichever of rank/final_rank isn't the sort key)
    dupe_rank_col = "rank" if sort_col == "final_rank" else "final_rank"
    if dupe_rank_col in display_table.columns:
        display_table = display_table.drop(columns=[dupe_rank_col])
    display_table = display_table.rename(columns={sort_col: "rank"})

    col_rename = {
        "rank": "Rank",
        "drug": "Drug",
        "reversal_score": "Reversal Score",
        "final_score": "Final Score",
        "safety_score": "Safety Score",
    }

    if "novelty_label" in display_table.columns:
        known_df = display_table[display_table["known_for_disease"]].drop(columns=["novelty_label", "known_for_disease"])
        novel_df = display_table[~display_table["known_for_disease"]].drop(columns=["novelty_label", "known_for_disease"])

        st.markdown('<span class="rpa-badge-known">🏆 KNOWN HIT — validation evidence</span>', unsafe_allow_html=True)
        if known_df.empty:
            st.caption("None of the currently displayed candidates are known RA drugs. Try increasing 'Candidates to display'.")
        else:
            render_table(known_df, rename=col_rename)

        st.markdown('<span class="rpa-badge-novel">🆕 NOVEL CANDIDATE</span>', unsafe_allow_html=True)
        if novel_df.empty:
            st.caption("No novel candidates in the current display window.")
        else:
            render_table(novel_df, rename=col_rename)
    else:
        render_table(display_table, rename=col_rename)

    csv_bytes = ranked.sort_values(sort_col).to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇ Download ranked candidates (CSV)",
        data=csv_bytes,
        file_name=f"repurposeai_{disease_name.replace(' ', '_')}_candidates.csv",
        mime="text/csv",
    )

    glow_divider()

    # ---- Explainability --------------------------------------------------
    render_section_header("search-network", "Why this candidate?", level="h3")
    selected_drug = st.selectbox("Drug", display_table["drug"].tolist())
    if selected_drug:
        try:
            genes_df = run_stage(
                "Gene-level explanation", top_contributing_genes, disease_vec, l1000_df[selected_drug], 10
            )
            genes_display = genes_df.copy()
            genes_display["direction"] = genes_display["direction"].map(
                {"reversed by drug": "✅ reversed", "reinforced by drug (unwanted)": "⚠️ reinforced"}
            ).fillna(genes_display["direction"])

            c1, c2 = st.columns([1, 1])
            with c1:
                render_table(
                    genes_display,
                    rename={
                        "gene": "Gene",
                        "disease_logFC": "Disease logFC",
                        "drug_zscore": "Drug Z-score",
                        "contribution": "Contribution",
                        "direction": "Direction",
                    },
                )
            with c2:
                st.bar_chart(genes_df.set_index("gene")["contribution"])

            reversed_genes = genes_df[genes_df["direction"] == "reversed by drug"]["gene"].tolist()
            if st.button("🌐 Try pathway enrichment for this candidate (needs internet)"):
                with st.spinner("Querying Enrichr..."):
                    pathways_df, note = _try_pathway_enrichment(reversed_genes)
                if pathways_df is not None and not pathways_df.empty:
                    render_table(pathways_df)
                else:
                    st.info(note or "No enriched pathways returned.")
        except StageError as e:
            st.error(f"⚠️ Explainability broke at **{e.stage}** — {e.original}")
            with st.expander("Technical details"):
                st.code(e.traceback_str)
else:
    if not st.session_state.get("pipeline_error"):
        st.info("Configure inputs in the sidebar and click **▶ Run pipeline** to begin.")

glow_divider()
with st.expander("🤔 Why not just use traditional repurposing or a generic ML screen?"):
    render_compare_strip()
