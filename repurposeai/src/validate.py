"""
validate.py
Day 4 morning module: retrospective validation. Run the pipeline on your chosen
disease and check whether it recovers a drug with a KNOWN, literature-documented
repurposing success -- this is your strongest evidence slide, stronger than any
feature list.

For Rheumatoid Arthritis specifically, good validation targets include:
  - JAK inhibitors (baricitinib, tofacitinib) -- baricitinib's RA-to-COVID-19
    repurposing is already cited in your deck (ACTT-2 trial), so recovering
    JAK-inhibitor-class candidates from an RA signature is a strong, on-theme result.
  - Anti-TNF biologics (etanercept, adalimumab) -- standard-of-care for RA;
    your pipeline should rank these highly since they're direct validation
    that the pipeline finds real, effective RA drugs, not noise.

Recovering a KNOWN drug is not a failure of "novelty" -- report it as proof the
method works, then separately highlight your top NOVEL candidates.
"""

from __future__ import annotations
import pandas as pd


# ---------------------------------------------------------------------------
# Ground truth for validation.
#
# Previously a hand-typed set of 9 drug names. Now derived from ChEMBL's
# drug_indication endpoint: a compound counts as a known reference drug for a
# disease if ChEMBL records the corresponding MeSH indication for it AT ANY
# PHASE.
#
# Why "any phase" and NOT max_phase == 4:
#   ChEMBL's max_phase_for_ind tracks the highest trial phase recorded for that
#   specific drug/indication pair, and it lags real-world approval status. On
#   the GSE70138 compound pool, filtering to phase 4 keeps 26 of the 80
#   RA-indicated compounds and DROPS tofacitinib, ruxolitinib and filgotinib --
#   i.e. it silently discards most of the drugs this pipeline is meant to
#   recover. Presence of the indication is the correct positive label; phase is
#   metadata about trial progress, not about whether the drug treats the disease.
#
#   (Note also that ChEMBL returns max_phase_for_ind as a STRING ("4.0"), so a
#   naive `phase == 4` comparison silently matches nothing at all.)
#
# indications.csv is built by scripts/build_lookup_tables.py from the ChEMBL
# pull; it has columns drug,indication,max_phase_for_ind.
# ---------------------------------------------------------------------------

import json
from pathlib import Path

_DATA_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"
_INDICATIONS_CSV = _DATA_DIR / "indications.csv"

# MeSH heading per disease, as ChEMBL spells it.
DISEASE_MESH = {
    "rheumatoid arthritis": "Arthritis, Rheumatoid",
}

# Fallback used only when indications.csv has not been built yet. This is the
# original hand-typed list -- it is NOT the ground truth when real data is
# present, and six of these nine are biologics that cannot appear in an L1000
# small-molecule screen at all.
_FALLBACK_SETS = {
    "rheumatoid arthritis": {
        "baricitinib", "tofacitinib", "upadacitinib",
        "etanercept", "adalimumab", "infliximab",
        "tocilizumab", "sarilumab",
        "methotrexate",
    },
}


def load_known_validation_set(disease_name: str) -> set[str]:
    """Drugs ChEMBL records as indicated for `disease_name`, at any trial phase."""
    key = disease_name.lower().strip()
    mesh = DISEASE_MESH.get(key)
    if mesh is None or not _INDICATIONS_CSV.exists():
        return set(_FALLBACK_SETS.get(key, set()))

    import csv
    out: set[str] = set()
    with _INDICATIONS_CSV.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if (row.get("indication") or "").strip() == mesh:
                drug = (row.get("drug") or "").strip()
                if drug:
                    out.add(drug)
    return out or set(_FALLBACK_SETS.get(key, set()))


class _LazyValidationSets(dict):
    """Keeps the KNOWN_VALIDATION_SETS[disease] access pattern working while
    sourcing the set from ChEMBL instead of a hard-coded literal."""

    def __missing__(self, key):
        s = load_known_validation_set(key)
        if not s:
            raise KeyError(key)
        self[key] = s
        return s

    def __contains__(self, key):
        try:
            self[key]
            return True
        except KeyError:
            return False


KNOWN_VALIDATION_SETS = _LazyValidationSets()


def check_recovery(ranked_candidates: pd.DataFrame, disease_name: str,
                    drug_col: str = "drug", top_k: int = 20) -> dict:
    """
    Check how many known reference drugs for `disease_name` appear in the
    top_k ranked candidates. Returns a summary dict ready to drop into the pitch.
    """
    key = disease_name.lower().strip()
    reference_set = KNOWN_VALIDATION_SETS.get(key)
    if reference_set is None:
        raise KeyError(
            f"No reference validation set defined for '{disease_name}'. "
            f"Add one to KNOWN_VALIDATION_SETS in validate.py. "
            f"Available: {list(KNOWN_VALIDATION_SETS)}"
        )

    top = ranked_candidates.head(top_k)
    top_names = {d.lower().strip() for d in top[drug_col]}
    recovered = reference_set & top_names

    return {
        "disease": disease_name,
        "top_k": top_k,
        "reference_set_size": len(reference_set),
        "recovered_drugs": sorted(recovered),
        "recovered_count": len(recovered),
        "recovery_rate": len(recovered) / len(reference_set) if reference_set else 0.0,
        "novel_candidates": [d for d in top[drug_col] if d.lower().strip() not in reference_set],
    }


def format_validation_statement(result: dict) -> str:
    """Human-readable one-liner for the pitch deck / demo narration."""
    if result["recovered_count"] == 0:
        return (
            f"No known {result['disease']} drugs were recovered in the top "
            f"{result['top_k']} candidates -- investigate signature quality before "
            f"presenting novel candidates as high-confidence."
        )
    recovered = ", ".join(result["recovered_drugs"])
    return (
        f"Blind-ran on {result['disease']}: the pipeline correctly surfaced "
        f"{result['recovered_count']}/{result['reference_set_size']} known effective "
        f"treatments ({recovered}) in the top {result['top_k']} candidates, "
        f"validating the method before surfacing {len(result['novel_candidates'])} "
        f"additional novel repurposing candidates."
    )


if __name__ == "__main__":
    print(__doc__)
