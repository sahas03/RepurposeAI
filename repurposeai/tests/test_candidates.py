"""
test_candidates.py
The two pipeline outputs must stay separate:
  VALIDATION  (validate.check_recovery)            -- known drugs, ranked by reversal alone
  CANDIDATES  (filters.screen_drugs -> rank_repurposing_candidates)
                                                    -- NOT-already-indicated drugs only,
                                                       ranked by reversal, safety as a gate

No real indication data exists in the repo yet, so these tests use the large mock
data's own placeholder drug names and pass a TEST-ONLY indications lookup that
designates one planted drug as "indicated". That exercises the logic without
inventing real drug/indication facts.

Run: python tests/test_candidates.py   (or: pytest tests/)
"""

import os
import sys
import tempfile

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import filters
import generate_mock_data_large
from data_loader import load_disease_signature, load_l1000_matrix, harmonize_genes
from filters import (screen_drugs, rank_repurposing_candidates, apply_novelty_filter,
                     STATUS_INDICATED, STATUS_NOT_REVERSING, STATUS_SAFETY_FAIL)
from signature_matching import score_reversal
from validate import check_recovery

DISEASE = "rheumatoid arthritis"
INDICATED = "planted_reversal_drug_1"               # strong reverser, marked as already indicated
NOVEL_STRONG = ["planted_reversal_drug_0", "planted_reversal_drug_2"]  # strong reversers, not indicated

# TEST FIXTURE on placeholder names -- not real indication data.
# Mixed case on purpose: indication sources (DrugBank) capitalize names, L1000 doesn't.
TEST_INDICATIONS = {"Planted_Reversal_Drug_1": {"Rheumatoid Arthritis", "some other condition"},
                    "drug_0010": {"some other condition"}}

_cache = {}


def _scores():
    if "scores" not in _cache:
        with tempfile.TemporaryDirectory() as tmp:
            meta = generate_mock_data_large.make_data(tmp)
            d = load_disease_signature(meta["disease_path"])
            l = load_l1000_matrix(meta["l1000_path"])
            d, l = harmonize_genes(d, l)
            _cache["scores"] = score_reversal(d, l)
            _cache["meta"] = meta
    return _cache["scores"], _cache["meta"]


def _candidates(top_n=20, **kw):
    scores, _ = _scores()
    screened = screen_drugs(scores, TEST_INDICATIONS, DISEASE, **kw)
    return screened, rank_repurposing_candidates(screened, top_n=top_n)


def test_known_drug_validates_via_reversal_alone():
    scores, _ = _scores()
    result = check_recovery(scores, DISEASE, top_k=10, reference_set={INDICATED})
    assert result["recovered_drugs"] == [INDICATED]
    assert result["reference_ranks"][INDICATED] == 1  # strongest planted reverser
    assert result["n_drugs_ranked"] == len(scores)


def test_validation_ignores_any_candidate_ordering():
    """Validation re-sorts by reversal score, so a candidates-style ordering can't leak in."""
    scores, _ = _scores()
    screened, _ = _candidates()
    shuffled = screened.sample(frac=1, random_state=0)  # any order, extra columns present
    a = check_recovery(scores, DISEASE, top_k=10, reference_set={INDICATED})
    b = check_recovery(shuffled, DISEASE, top_k=10, reference_set={INDICATED})
    assert a == b


def test_known_drug_excluded_from_candidates():
    screened, cands = _candidates(top_n=None)
    assert INDICATED not in set(cands["drug"])
    row = screened.set_index("drug").loc[INDICATED]
    assert row["candidate_status"] == STATUS_INDICATED and not row["is_novel"]
    # a drug with a different indication is still novel
    assert screened.set_index("drug").loc["drug_0010", "is_novel"]


def test_novel_strong_reverser_ranks_top_of_candidates():
    _, cands = _candidates()
    assert list(cands["drug"][:2]) == sorted(NOVEL_STRONG, key=lambda d: cands.set_index("drug").loc[d, "reversal_score"])
    # all non-indicated planted reversers are in the top 10 candidates
    _, meta = _scores()
    assert set(meta["planted_reversal"]) - {INDICATED} <= set(cands["drug"].head(10))
    assert list(cands["candidate_rank"]) == list(range(1, len(cands) + 1))
    assert cands["reversal_score"].is_monotonic_increasing


def test_indicated_reverser_in_validation_not_candidates():
    scores, _ = _scores()
    _, cands = _candidates(top_n=None)
    val = check_recovery(scores, DISEASE, top_k=20, reference_set={INDICATED})
    assert INDICATED in val["recovered_drugs"]
    assert INDICATED not in set(cands["drug"])


def test_non_reversing_drugs_never_candidates():
    screened, cands = _candidates(top_n=None)
    assert (cands["reversal_score"] < 0).all()
    _, meta = _scores()
    for d in meta["planted_reinforcing"]:
        assert screened.set_index("drug").loc[d, "candidate_status"] == STATUS_NOT_REVERSING


def test_default_reference_set_finds_nothing_on_mock_names():
    """Real RA reference drugs aren't in mock data -> 0 recovered (correct, not a bug)."""
    scores, _ = _scores()
    assert check_recovery(scores, DISEASE, top_k=20)["recovered_count"] == 0


def test_indication_alias_matches():
    df = pd.DataFrame({"drug": ["a", "b"]})
    out = apply_novelty_filter(df, {"a": {"Arthritis, Rheumatoid"}}, DISEASE)
    assert list(out["known_for_disease"]) == [True, False]
    assert list(out["is_novel"]) == [False, True]


def test_safety_is_a_gate_not_a_weight():
    """
    Lipinski is pass/fail (<=1 violation passes); passing drugs keep pure reversal order.
    rdkit isn't required: lipinski_violations is stubbed with fixed violation counts.
    """
    stub = {"S0": 0, "S1": 1, "S2": 2}
    original = filters.lipinski_violations
    filters.lipinski_violations = lambda smiles: stub.get(smiles)
    try:
        smiles = {"planted_reversal_drug_0": "S2",   # strong reverser, fails the gate
                  "planted_reversal_drug_2": "S1",   # passes (1 violation)
                  "planted_reversal_drug_3": "S0",
                  "planted_reversal_drug_4": "unparsable"}
        screened, cands = _candidates(smiles_lookup=smiles)
    finally:
        filters.lipinski_violations = original

    s = screened.set_index("drug")
    assert s.loc["planted_reversal_drug_0", "candidate_status"] == STATUS_SAFETY_FAIL
    assert "planted_reversal_drug_0" not in set(cands["drug"])
    assert s.loc["planted_reversal_drug_4", "safety_status"] == "not screened"
    assert "planted_reversal_drug_4" in set(cands["drug"])
    # no soft safety score in the ranking: order is pure reversal
    assert cands["reversal_score"].is_monotonic_increasing
    assert "safety_score" not in cands.columns and "final_score" not in cands.columns


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"PASSED {t.__name__}")
    print(f"\nALL {len(tests)} CANDIDATE/VALIDATION TESTS PASSED")


if __name__ == "__main__":
    main()
