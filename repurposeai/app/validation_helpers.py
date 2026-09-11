"""
validation_helpers.py
Extends src/validate.py's real KNOWN_VALIDATION_SETS-based recovery check
with an honest fallback for synthetic mock data.

On mock data, drug names are placeholders like "planted_reversal_drug_0",
not real RA drug identities -- validate.check_recovery() correctly finds
zero matches against KNOWN_VALIDATION_SETS there. That's correct behavior,
not a bug, but it would leave the validation panel blank during a mock-data
demo. This module adds a clearly-labeled *synthetic* sanity check for that
case, built from the planted-drug naming convention that
scripts/generate_mock_data.py already uses (and tests/test_pipeline.py
already relies on), so the panel never claims a placeholder is a real drug.
"""

from __future__ import annotations

import pandas as pd

PLANTED_REVERSAL_PREFIX = "planted_reversal_drug"
PLANTED_REINFORCING_PREFIX = "planted_reinforcing_drug"


def has_real_validation_signal(l1000_columns, known_drugs: set) -> bool:
    """True if any real reference drug name for this disease is present in the drug library."""
    cols = {str(c).lower() for c in l1000_columns}
    return bool({d.lower() for d in known_drugs} & cols)


def synthetic_ground_truth_check(ranked: pd.DataFrame, l1000_columns, top_k: int) -> dict | None:
    """
    Mock-data sanity check: do the planted reversal drugs land near the top,
    and do the planted reinforcing (bad) drugs stay near the bottom?
    Returns None if no planted-drug naming convention is detected (e.g. a
    custom upload with unknown drug names) so callers can fall back further.
    """
    cols = list(l1000_columns)
    reversal_planted = [c for c in cols if str(c).startswith(PLANTED_REVERSAL_PREFIX)]
    reinforcing_planted = [c for c in cols if str(c).startswith(PLANTED_REINFORCING_PREFIX)]
    if not reversal_planted:
        return None

    top = set(ranked.head(top_k)["drug"])
    recovered = sorted(set(reversal_planted) & top)
    reinforcing_ranks = ranked[ranked["drug"].isin(reinforcing_planted)]

    return {
        "recovered": recovered,
        "recovered_count": len(recovered),
        "planted_total": len(reversal_planted),
        "recovery_rate": (len(recovered) / len(reversal_planted)) if reversal_planted else 0.0,
        "reinforcing_planted": reinforcing_planted,
        "reinforcing_ranks": reinforcing_ranks,
    }
