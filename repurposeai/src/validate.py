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


# Known reference drugs for validation -- extend this list as you research
# your chosen disease further during Day 1-2.
KNOWN_VALIDATION_SETS = {
    "rheumatoid arthritis": {
        "baricitinib", "tofacitinib", "upadacitinib",       # JAK inhibitors
        "etanercept", "adalimumab", "infliximab",             # anti-TNF
        "tocilizumab", "sarilumab",                            # anti-IL6
        "methotrexate",                                        # conventional DMARD
    },
}


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
