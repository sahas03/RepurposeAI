"""
filters.py
Day 3 module: turn a raw ranked list into a safety- and novelty-aware shortlist.

Two practical, buildable-in-a-day proxies (NOT full ADMET modeling):
  1. safety_score  -- Lipinski's Rule of Five via RDKit, as a crude druglikeness/
                       safety proxy, plus an optional "already approved" bonus
                       if you have DrugBank approval status.
  2. novelty_score -- flags whether a drug is already documented for the target
                       disease (known hit) vs. not (novel repurposing candidate).
                       Both are valuable to show; label them, don't discard "known"
                       hits -- they're your validation evidence.
"""

from __future__ import annotations
import pandas as pd

try:
    from rdkit import Chem
    from rdkit.Chem import Descriptors, Lipinski
    RDKIT_AVAILABLE = True
except ImportError:
    RDKIT_AVAILABLE = False


def lipinski_safety_score(smiles: str) -> float:
    """
    Returns a 0-1 druglikeness proxy score based on Lipinski's Rule of Five.
    1.0 = passes all 4 rules, 0.0 = fails all 4. Not a substitute for real ADMET,
    but a legitimate, fast, defensible screen for a hackathon MVP.
    """
    if not RDKIT_AVAILABLE:
        raise ImportError("rdkit is required for lipinski_safety_score(). pip install rdkit")

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return 0.5  # unknown / unparsable structure -> neutral score, flag for manual review

    mw = Descriptors.MolWt(mol)
    logp = Descriptors.MolLogP(mol)
    hbd = Lipinski.NumHDonors(mol)
    hba = Lipinski.NumHAcceptors(mol)

    checks = [mw <= 500, logp <= 5, hbd <= 5, hba <= 10]
    return sum(checks) / len(checks)


def apply_safety_filter(candidates: pd.DataFrame, smiles_lookup: dict[str, str],
                         approved_set: set[str] | None = None) -> pd.DataFrame:
    """
    candidates: DataFrame with a 'drug' column (from signature_matching.rank_candidates)
    smiles_lookup: dict mapping drug name -> SMILES string (from DrugBank/ChEMBL export)
    approved_set: optional set of drug names known to be FDA-approved (safety bonus)
    """
    out = candidates.copy()
    scores = []
    for drug in out["drug"]:
        smiles = smiles_lookup.get(drug)
        if smiles is None:
            scores.append(0.5)  # unknown structure, neutral
            continue
        score = lipinski_safety_score(smiles)
        if approved_set and drug in approved_set:
            score = min(1.0, score + 0.2)  # approved-drug bonus
        scores.append(score)
    out["safety_score"] = scores
    return out


# Novelty label states. Three, not two: a drug that was trialled for the
# disease but never approved is neither validation evidence nor a novel
# discovery, and collapsing it into either one misrepresents it.
LABEL_APPROVED = "known hit (approved)"
LABEL_INVESTIGATIONAL = "reported RA investigation (not approved)"
LABEL_NOVEL = "novel candidate"

# Indication-string convention (see data/raw/ra_indications.json):
#   "<disease>"               -> approved for that disease
#   "<disease> (<qualifier>)" -> a weaker, qualified relationship. Only a
#                                qualifier containing "investigational" earns
#                                its own label; anything else (e.g. a failed
#                                trial) is deliberately NOT treated as evidence.
INVESTIGATIONAL_QUALIFIER = "investigational"


def apply_novelty_filter(candidates: pd.DataFrame, known_indications: dict[str, set[str]],
                          disease_name: str) -> pd.DataFrame:
    """
    known_indications: dict mapping drug name -> set of documented disease indications
                        (from DrugBank's indication field)
    disease_name: the disease you're targeting, used to check documented status
    """
    out = candidates.copy()
    target = disease_name.lower().strip()
    qualified_prefix = target + " ("

    def _classify(drug: str) -> str:
        indications = {str(x).lower() for x in known_indications.get(drug, set())}
        if target in indications:
            return LABEL_APPROVED
        if any(i.startswith(qualified_prefix) and INVESTIGATIONAL_QUALIFIER in i
               for i in indications):
            return LABEL_INVESTIGATIONAL
        return LABEL_NOVEL

    out["novelty_label"] = out["drug"].apply(_classify)
    # Stays boolean and approved-only: combine_scores()'s novelty bonus and the
    # dashboard's known/novel table split both read this column.
    out["known_for_disease"] = out["novelty_label"] == LABEL_APPROVED
    return out


def combine_scores(candidates: pd.DataFrame,
                    weights: dict[str, float] | None = None) -> pd.DataFrame:
    """
    Combine reversal_score (lower/more negative = better), safety_score (higher = better),
    and novelty into one final ranking. Reversal score is inverted and min-max scaled
    to [0,1] first so all components are on the same "higher = better" scale.

    weights default: reversal 0.6, safety 0.2, novelty_bonus 0.2
    """
    if weights is None:
        weights = {"reversal": 0.6, "safety": 0.2, "novelty": 0.2}

    out = candidates.copy()
    r = out["reversal_score"]
    r_scaled = (r.max() - r) / (r.max() - r.min() + 1e-9)  # invert: more negative -> closer to 1
    novelty_bonus = out.get("known_for_disease", pd.Series(False, index=out.index)).map({True: 1.0, False: 0.6})

    out["final_score"] = (
        weights["reversal"] * r_scaled
        + weights["safety"] * out.get("safety_score", 0.5)
        + weights["novelty"] * novelty_bonus
    )
    out = out.sort_values("final_score", ascending=False).reset_index(drop=True)
    out["final_rank"] = out.index + 1
    return out


if __name__ == "__main__":
    print(__doc__)
