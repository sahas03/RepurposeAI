"""
filters.py
Day 3 module: turn raw reversal scores into the REPURPOSING CANDIDATES list.

This module produces the candidates output only. Proving the method works
(recovering known drugs) is a separate output -- see validate.py, which ranks
by reversal score alone and never uses anything in this file.

Candidate screen, in order (each is a hard pass/fail -- no blended weights):
  1. novelty   -- a drug is NOVEL if it is NOT already indicated for the target
                  disease (per an indications lookup, e.g. DrugBank/ChEMBL).
                  Already-indicated drugs are excluded from candidates; they
                  belong in validation, not in "new uses".
  2. reversal  -- the drug must actually reverse the signature (score < 0).
  3. safety    -- Lipinski's Rule of Five via RDKit as a druglikeness gate:
                  pass with <= 1 violation (Lipinski's own criterion). Drugs with
                  no SMILES (e.g. biologics) are kept but marked "not screened".
Survivors are ranked by reversal score (most negative first).
"""

from __future__ import annotations
import pandas as pd

from signature_matching import check_scores, sort_scores

try:
    from rdkit import Chem
    from rdkit.Chem import Descriptors, Lipinski
    RDKIT_AVAILABLE = True
except ImportError:
    RDKIT_AVAILABLE = False


# Alternate names for a disease as they appear in indication sources
# (e.g. ChEMBL's drug_indication uses MeSH headings like "Arthritis, Rheumatoid").
DISEASE_ALIASES = {
    "rheumatoid arthritis": {"rheumatoid arthritis", "arthritis, rheumatoid"},
}

STATUS_CANDIDATE = "candidate"
STATUS_INDICATED = "excluded: already indicated for disease"
STATUS_NOT_REVERSING = "excluded: does not reverse signature"
STATUS_SAFETY_FAIL = "excluded: failed Lipinski safety gate"


def lipinski_violations(smiles: str) -> int | None:
    """
    Number of Lipinski Rule-of-Five violations (0-4) for a SMILES string,
    or None if the structure can't be parsed (flag for manual review).
    """
    if not RDKIT_AVAILABLE:
        raise ImportError("rdkit is required for Lipinski screening. pip install rdkit")

    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return None

    checks = [
        Descriptors.MolWt(mol) <= 500,
        Descriptors.MolLogP(mol) <= 5,
        Lipinski.NumHDonors(mol) <= 5,
        Lipinski.NumHAcceptors(mol) <= 10,
    ]
    return len(checks) - sum(checks)


def lipinski_safety_score(smiles: str) -> float:
    """
    Returns a 0-1 druglikeness proxy score based on Lipinski's Rule of Five.
    1.0 = passes all 4 rules, 0.0 = fails all 4. Not a substitute for real ADMET,
    but a legitimate, fast, defensible screen for a hackathon MVP.
    Informational only -- the candidate screen uses the pass/fail gate, not this score.
    """
    violations = lipinski_violations(smiles)
    if violations is None:
        return 0.5  # unknown / unparsable structure -> neutral score, flag for manual review
    return (4 - violations) / 4


def apply_safety_filter(candidates: pd.DataFrame, smiles_lookup: dict[str, str],
                         approved_set: set[str] | None = None,
                         max_violations: int = 1) -> pd.DataFrame:
    """
    candidates: DataFrame with a 'drug' column
    smiles_lookup: dict mapping drug name -> SMILES string (from DrugBank/ChEMBL export)
    approved_set: optional set of drug names known to be FDA-approved (shown as info only)

    Adds:
      lipinski_violations -- 0-4, or NA if no/unparsable structure
      safety_status       -- "pass" (<= max_violations), "fail", or "not screened"
      approved            -- only if approved_set is given
    """
    out = candidates.copy()
    smiles_lower = {str(k).lower().strip(): v for k, v in smiles_lookup.items()}
    violations = []
    for drug in out["drug"]:
        smiles = smiles_lower.get(str(drug).lower().strip())
        violations.append(None if smiles is None else lipinski_violations(smiles))
    out["lipinski_violations"] = pd.array(violations, dtype="Int64")
    out["safety_status"] = [
        "not screened" if v is None else ("pass" if v <= max_violations else "fail")
        for v in violations
    ]
    if approved_set is not None:
        approved_lower = {a.lower().strip() for a in approved_set}
        out["approved"] = out["drug"].map(lambda d: str(d).lower().strip() in approved_lower)
    return out


def is_indicated_for(indications, disease_name: str) -> bool:
    """True if any of a drug's documented indications names the disease (or an alias)."""
    names = DISEASE_ALIASES.get(disease_name.lower().strip(), set()) | {disease_name.lower().strip()}
    return any(str(x).lower().strip() in names for x in (indications or ()))


def apply_novelty_filter(candidates: pd.DataFrame, known_indications: dict[str, set[str]],
                          disease_name: str) -> pd.DataFrame:
    """
    Flag each drug as already indicated for `disease_name` or novel.

    known_indications: dict mapping drug name -> iterable of documented indications
        (e.g. built from DrugBank's indication field or ChEMBL's drug_indication table).
        Drug names are matched case-insensitively, so "Methotrexate" (DrugBank) matches
        "methotrexate" (L1000 pert_iname). Drugs missing from the lookup count as novel.

    Adds:
      known_for_disease -- True if already indicated for the disease
      is_novel          -- True if NOT already indicated (a repurposing candidate)
      novelty_label
    """
    lookup = {str(k).lower().strip(): v for k, v in known_indications.items()}
    out = candidates.copy()
    out["known_for_disease"] = out["drug"].map(
        lambda d: is_indicated_for(lookup.get(str(d).lower().strip()), disease_name)
    ).astype(bool)
    out["is_novel"] = ~out["known_for_disease"]
    out["novelty_label"] = out["is_novel"].map(
        {True: "novel candidate", False: "already indicated (validation only)"}
    )
    return out


def screen_drugs(scores: pd.Series, known_indications: dict[str, set[str]], disease_name: str,
                 smiles_lookup: dict[str, str] | None = None,
                 approved_set: set[str] | None = None,
                 max_violations: int = 1, max_reversal_score: float = 0.0) -> pd.DataFrame:
    """
    Run the candidate screen over EVERY scored drug and record why each one is kept
    or excluded (column candidate_status). Use rank_repurposing_candidates() on the
    result to get the ranked candidates list.

    scores: reversal scores for all drugs (signature_matching output; more negative
            = stronger reversal). Pass the full series, not a top-N slice, so
            exclusions don't shrink the candidate list.
    smiles_lookup: optional; without it every drug is "not screened" for safety.
    Raises on NaN scores or duplicate drug names rather than misclassifying them.
    """
    check_scores(scores)
    out = sort_scores(scores).rename("reversal_score").rename_axis("drug").reset_index()
    out["reversal_rank"] = range(1, len(out) + 1)
    out = apply_novelty_filter(out, known_indications, disease_name)

    status = pd.Series(STATUS_CANDIDATE, index=out.index)
    status[out["reversal_score"] >= max_reversal_score] = STATUS_NOT_REVERSING
    status[out["known_for_disease"]] = STATUS_INDICATED

    if smiles_lookup is not None:
        # Only structure-check drugs still in the running (RDKit parsing is the slow part)
        alive = status == STATUS_CANDIDATE
        safety = apply_safety_filter(out.loc[alive, ["drug"]], smiles_lookup, approved_set, max_violations)
        out = out.join(safety.drop(columns="drug"))
        status[out["safety_status"] == "fail"] = STATUS_SAFETY_FAIL
    else:
        out["safety_status"] = "not screened"

    out["candidate_status"] = status
    return out


def rank_repurposing_candidates(screened: pd.DataFrame, top_n: int | None = 20) -> pd.DataFrame:
    """
    CANDIDATES OUTPUT: drugs that passed every gate in screen_drugs(), ranked by
    reversal score alone (most negative first). Already-indicated drugs are never
    in this list -- see validate.check_recovery for those.
    """
    # reversal_rank already encodes score order with a deterministic tie-break
    out = screened[screened["candidate_status"] == STATUS_CANDIDATE].sort_values("reversal_rank")
    if top_n is not None:
        out = out.head(top_n)
    out = out.drop(columns=["candidate_status", "known_for_disease", "is_novel", "novelty_label"])
    out.insert(0, "candidate_rank", range(1, len(out) + 1))
    return out.reset_index(drop=True)


if __name__ == "__main__":
    print(__doc__)
