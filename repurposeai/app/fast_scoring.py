"""
fast_scoring.py
Optional vectorized reimplementation of
src/signature_matching.py::cosine_reversal_score.

FLAGGED FOR THE TEAM: this intentionally lives outside src/ instead of
editing signature_matching.py directly, since that file is owned by
whoever is building Phase 2 and is actively changing overnight. It is not
imported by anything in src/, so it can't break teammates' code -- but it
CAN silently drift out of sync with their logic if cosine_reversal_score's
behavior changes there. The dashboard exposes it as an opt-in "fast mode"
toggle (see app/dashboard.py) rather than a silent replacement.

Same contract, same math as the original: cosine similarity between the
disease vector and each drug column, sorted ascending (most negative =
best reversal candidate). The only difference is *how* it's computed --
one matrix multiply across all drug columns at once instead of a Python
for-loop over each column individually. On the 150-drug mock matrix the
loop is invisible; on a real L1000 library (thousands of drug signatures)
the loop can visibly stall a live demo, so this exists as a safety valve.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def cosine_reversal_score_fast(disease_vec: pd.Series, l1000_df: pd.DataFrame) -> pd.Series:
    """Vectorized drop-in replacement for signature_matching.cosine_reversal_score."""
    genes = disease_vec.index
    d = disease_vec.values.astype(float)
    d_norm = np.linalg.norm(d)
    if d_norm == 0:
        raise ValueError("Disease vector has zero norm; check input signature.")

    v = l1000_df.loc[genes].values.astype(float)  # genes x drugs
    v_norms = np.linalg.norm(v, axis=0)

    with np.errstate(divide="ignore", invalid="ignore"):
        cos_sim = (d @ v) / (d_norm * v_norms)
    cos_sim = np.where(v_norms == 0, 0.0, cos_sim)

    result = pd.Series(cos_sim, index=l1000_df.columns, name="cosine_similarity").sort_values()
    return result
