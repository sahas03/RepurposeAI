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

This is the VALIDATION output, and it is deliberately separate from the
candidates output (filters.rank_repurposing_candidates): it ranks drugs by
REVERSAL SCORE ALONE -- no novelty, no safety -- because it's a calibration
test of the scoring method, not a shortlist.
"""

from __future__ import annotations
import pandas as pd

from signature_matching import check_scores, sort_scores


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


def check_recovery(reversal_scores: pd.Series | pd.DataFrame, disease_name: str,
                    drug_col: str = "drug", top_k: int = 20,
                    reference_set: set[str] | None = None) -> dict:
    """
    Check how many known reference drugs for `disease_name` rank in the top_k
    drugs BY REVERSAL SCORE ALONE. Returns a summary dict ready to drop into the pitch.

    reversal_scores: signature_matching scores for all drugs -- a Series indexed by
        drug, or a DataFrame with drug_col + "reversal_score" columns. It is always
        re-sorted by reversal score here, so a novelty- or safety-adjusted ordering
        can't leak into the calibration check. Pass ALL drugs, not a filtered list:
        candidate lists exclude known drugs by design.
    reference_set: known drugs to look for; defaults to KNOWN_VALIDATION_SETS[disease].
    """
    if reference_set is None:
        reference_set = KNOWN_VALIDATION_SETS.get(disease_name.lower().strip())
        if reference_set is None:
            raise KeyError(
                f"No reference validation set defined for '{disease_name}'. "
                f"Add one to KNOWN_VALIDATION_SETS in validate.py. "
                f"Available: {list(KNOWN_VALIDATION_SETS)}"
            )
    reference_set = {d.lower().strip() for d in reference_set}

    if isinstance(reversal_scores, pd.DataFrame):
        reversal_scores = reversal_scores.set_index(drug_col)["reversal_score"]
    check_scores(reversal_scores)  # NaN scores or duplicate names would corrupt ranks
    ordered = [str(d).lower().strip() for d in sort_scores(reversal_scores).index]
    ranks = {d: i + 1 for i, d in enumerate(ordered)}

    recovered = {d for d in reference_set if ranks.get(d, top_k + 1) <= top_k}
    in_library = reference_set & ranks.keys()

    return {
        "disease": disease_name,
        "top_k": top_k,
        "n_drugs_ranked": len(ordered),
        "reference_set_size": len(reference_set),
        "reference_in_library": len(in_library),  # e.g. biologics are absent from L1000
        "reference_ranks": {d: ranks[d] for d in sorted(in_library, key=ranks.get)},
        "recovered_drugs": sorted(recovered),
        "recovered_count": len(recovered),
        "recovery_rate": len(recovered) / len(reference_set) if reference_set else 0.0,
    }


def format_validation_statement(result: dict) -> str:
    """Human-readable one-liner for the pitch deck / demo narration."""
    if result["recovered_count"] == 0:
        return (
            f"No known {result['disease']} drugs ranked in the top {result['top_k']} "
            f"by reversal score -- investigate signature quality before "
            f"presenting novel candidates as high-confidence."
        )
    recovered = ", ".join(result["recovered_drugs"])
    return (
        f"Blind-ran on {result['disease']}: ranking purely by gene-expression reversal, "
        f"the method placed {result['recovered_count']}/{result['reference_set_size']} known "
        f"effective treatments ({recovered}) in the top {result['top_k']} of "
        f"{result['n_drugs_ranked']} drugs -- evidence the scoring picks up real signal."
    )


if __name__ == "__main__":
    print(__doc__)
