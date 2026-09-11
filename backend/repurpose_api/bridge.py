"""
bridge.py
The single import seam between this service and the verified pipeline.

Design rule for this whole backend: there is exactly ONE scoring engine in this
project, and it lives in repurposeai/src/. Nothing here reimplements loading,
scoring, filtering or validation -- this module puts src/ (and the dashboard's
app/ helpers) on sys.path the same way app/dashboard.py does, imports the real
functions, and every other module in the service calls through here.

If a teammate changes a signature in src/ overnight, this file and the call
sites in orchestrator.py are the only places that need looking at.
"""

from __future__ import annotations

import sys

from . import config

# src/ modules import each other flatly (`from data_loader import ...`), so the
# directory itself has to be on sys.path -- same as dashboard.py does.
for _path in (config.SRC_DIR, config.PIPELINE_APP_DIR):
    _s = str(_path)
    if _s not in sys.path:
        sys.path.insert(0, _s)

# --- repurposeai/src -- the real pipeline ---------------------------------
from data_loader import (  # noqa: E402
    load_disease_signature,
    load_l1000_matrix,
    harmonize_genes,
    zscore_disease_signature,
)
from signature_matching import (  # noqa: E402
    score_reversal,
    rank_candidates,
    SCORING_METHODS,
)
from filters import (  # noqa: E402
    apply_safety_filter,
    apply_novelty_filter,
    combine_scores,
    RDKIT_AVAILABLE,
)
from interpretability import (  # noqa: E402
    explain_candidate,
    pathway_enrichment,
    GSEAPY_AVAILABLE,
)
from validate import (  # noqa: E402
    check_recovery,
    format_validation_statement,
    KNOWN_VALIDATION_SETS,
)

# --- repurposeai/app -- dashboard helpers worth reusing, not rewriting ----
# pipeline.py is pure stdlib and validation_helpers.py is pure pandas; neither
# pulls in Streamlit, so importing them here costs nothing.
from pipeline import run_stage, StageError  # noqa: E402
from validation_helpers import (  # noqa: E402
    has_real_validation_signal,
    synthetic_ground_truth_check,
)

__all__ = [
    "load_disease_signature",
    "load_l1000_matrix",
    "harmonize_genes",
    "zscore_disease_signature",
    "score_reversal",
    "rank_candidates",
    "SCORING_METHODS",
    "apply_safety_filter",
    "apply_novelty_filter",
    "combine_scores",
    "RDKIT_AVAILABLE",
    "explain_candidate",
    "pathway_enrichment",
    "GSEAPY_AVAILABLE",
    "check_recovery",
    "format_validation_statement",
    "KNOWN_VALIDATION_SETS",
    "run_stage",
    "StageError",
    "has_real_validation_signal",
    "synthetic_ground_truth_check",
]
