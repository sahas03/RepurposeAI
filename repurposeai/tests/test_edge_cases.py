"""
test_edge_cases.py
Degenerate / edge-case inputs, run through the ACTUAL pipeline functions on small
synthetic data built here (no real data). Each test pins the intended behavior:
either handled correctly, or a loud, clear error -- never a silent wrong answer.

Run: pytest tests/test_edge_cases.py
"""

import io
import os
import sys
import warnings

import numpy as np
import pandas as pd
import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))
sys.path.insert(0, os.path.join(ROOT, "app"))

from data_loader import (harmonize_genes, load_l1000_matrix, zscore_disease_signature,
                         MIN_SHARED_GENES)
from signature_matching import (cosine_reversal_score, weighted_connectivity_score,
                                score_reversal, rank_candidates)
from filters import (screen_drugs, rank_repurposing_candidates, STATUS_CANDIDATE,
                     STATUS_INDICATED, STATUS_NOT_REVERSING)
from validate import check_recovery, format_validation_statement
from interpretability import top_contributing_genes

DISEASE = "rheumatoid arthritis"
N_GENES = 40
GENES = [f"G{i}" for i in range(N_GENES)]


def _disease(logfc=None, genes=GENES):
    if logfc is None:
        rng = np.random.default_rng(1)
        half = len(genes) // 2
        logfc = np.r_[rng.normal(2, 0.3, half), rng.normal(-2, 0.3, len(genes) - half)]
    return pd.DataFrame({"gene": genes, "logFC": logfc, "pvalue": 0.01})


def _library(n_noise=5, seed=2, **drugs):
    """Noise drugs plus named drug columns (genes x drugs)."""
    rng = np.random.default_rng(seed)
    lib = pd.DataFrame(rng.normal(size=(N_GENES, n_noise)), index=GENES,
                       columns=[f"noise_{i}" for i in range(n_noise)])
    for name, col in drugs.items():
        lib[name] = col
    return lib


def _reverser(noise_sd=0.3, seed=3):
    rng = np.random.default_rng(seed)
    return -_disease()["logFC"].to_numpy() + rng.normal(0, noise_sd, N_GENES)


def _both_scores(disease_df, lib):
    return {"cosine": score_reversal(disease_df, lib, method="cosine"),
            "wtcs": score_reversal(disease_df, lib, method="wtcs")}


# ---------------------------------------------------------------------------
# 1. All-zero drug column
# ---------------------------------------------------------------------------
def test_all_zero_drug_scores_exactly_zero_without_nan_or_warnings():
    dis = _disease()
    lib = _library(zero=np.zeros(N_GENES))
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)  # no hidden divide-by-zero
        scores = _both_scores(dis, lib)
        unweighted = weighted_connectivity_score(dis, lib, weighted=False)

    for s in [*scores.values(), unweighted]:
        assert s["zero"] == 0.0 and np.isfinite(s).all()

    # 0.0 means "reverses nothing": excluded from candidates, never ranked as a reverser
    screened = screen_drugs(scores["cosine"], {}, DISEASE).set_index("drug")
    assert screened.loc["zero", "candidate_status"] == STATUS_NOT_REVERSING

    # Documented limitation: the undefined cosine of a zero vector is reported as the
    # same 0.0 as an exactly-orthogonal drug -- the score alone can't tell them apart.
    d = zscore_disease_signature(dis).to_numpy()
    r = np.random.default_rng(4).normal(size=N_GENES)
    orthogonal = r - (r @ d) / (d @ d) * d
    lib2 = _library(zero=np.zeros(N_GENES), orthogonal=orthogonal)
    s2 = cosine_reversal_score(zscore_disease_signature(dis), lib2)
    assert s2["zero"] == 0.0 and s2["orthogonal"] == pytest.approx(0.0, abs=1e-12)


def test_all_zero_drug_explanation_says_no_change_not_reinforced():
    """FIXED: zero contributions used to be labeled 'reinforced by drug (unwanted)'."""
    dv = zscore_disease_signature(_disease())
    genes_df = top_contributing_genes(dv, pd.Series(0.0, index=GENES), top_n=5)
    assert set(genes_df["direction"]) == {"no change"}


# ---------------------------------------------------------------------------
# 2. Tied scores
# ---------------------------------------------------------------------------
TIED = ["tie_c", "tie_a", "tie_e", "tie_b", "tie_d"]


def _tied_library():
    col = _reverser()
    return _library(n_noise=30, **{name: col for name in TIED})


@pytest.mark.parametrize("method", ["cosine", "wtcs"])
def test_tied_scores_rank_deterministically_regardless_of_column_order(method):
    """FIXED: tie order used to follow column order, flipping validation results."""
    dis, lib = _disease(), _tied_library()
    rng = np.random.default_rng(5)
    perms = [list(lib.columns), list(lib.columns[::-1])] + [list(rng.permutation(lib.columns)) for _ in range(5)]

    orders, candidate_orders, recoveries = set(), set(), set()
    for cols in perms + perms[:2]:  # repeated runs too
        scores = score_reversal(dis, lib[cols], method=method)
        assert scores[TIED].nunique() == 1, "test setup: tied drugs must score identically"
        orders.add(tuple(scores.index))
        cands = rank_repurposing_candidates(screen_drugs(scores, {}, DISEASE), top_n=None)
        candidate_orders.add(tuple(cands["drug"]))
        # a tied drug right at the top-K boundary must be in or out consistently
        recoveries.add(check_recovery(scores, DISEASE, top_k=3, reference_set={"tie_d"})["recovered_count"])

    assert len(orders) == 1 and len(candidate_orders) == 1 and len(recoveries) == 1
    ranked = list(next(iter(orders)))
    assert [d for d in ranked if d in TIED] == sorted(TIED)  # ties broken by drug name
    assert ranked[:5] == sorted(TIED)


def test_rank_candidates_tie_order_matches_screen():
    scores = score_reversal(_disease(), _tied_library())
    top = rank_candidates(scores, top_n=5)
    assert list(top["drug"]) == sorted(TIED)


# ---------------------------------------------------------------------------
# 3. Empty gene overlap
# ---------------------------------------------------------------------------
def _disjoint_library():
    return pd.DataFrame(np.random.default_rng(6).normal(size=(N_GENES, 3)),
                        index=[f"OTHER{i}" for i in range(N_GENES)], columns=["a", "b", "c"])


def test_disjoint_genes_fail_loudly_with_clear_error():
    dis, lib = _disease(), _disjoint_library()
    with pytest.raises(ValueError, match="Only 0 shared genes"):
        harmonize_genes(dis, lib)
    with pytest.raises(ValueError, match="No shared genes"):
        cosine_reversal_score(zscore_disease_signature(dis), lib)
    with pytest.raises(ValueError, match="No shared genes"):  # FIXED: was "loosen thresholds"
        weighted_connectivity_score(dis, lib)
    with pytest.raises(ValueError, match="No shared genes"):
        score_reversal(dis, lib)


def test_partially_missing_genes_give_clear_error_for_cosine():
    dis = _disease()
    lib = _library().iloc[:-3]  # drop 3 disease genes from the matrix
    with pytest.raises(ValueError, match="3 of 40 disease genes are missing"):
        score_reversal(dis, lib)


# ---------------------------------------------------------------------------
# 4. Single shared gene
# ---------------------------------------------------------------------------
def test_single_shared_gene_is_rejected_not_scored_confidently():
    """FIXED: 1 gene used to give every drug exactly -1.0 (or all-NaN via z-scoring)."""
    dis = _disease()  # full 40-gene signature...
    lib = _library().rename(index=lambda g: g if g == "G0" else f"OTHER_{g}")  # ...only G0 shared
    with pytest.raises(ValueError, match="Only 1 shared genes"):
        harmonize_genes(dis, lib)
    with pytest.raises(ValueError, match="Only 1 shared gene"):
        weighted_connectivity_score(dis, lib)
    with pytest.raises(ValueError, match="39 of 40 disease genes are missing"):
        score_reversal(dis, lib)

    # Caller restricted everything to the single shared gene before scoring
    one, lib1 = dis.iloc[[0]], lib.loc[["G0"]]
    with pytest.raises(ValueError, match="Only 1 shared gene"):
        cosine_reversal_score(pd.Series([2.0], index=["G0"]), lib1)  # used to give every drug -1.0
    with pytest.raises(ValueError, match="zero variance"):
        score_reversal(one, lib1)  # z-scoring one value divides 0 by 0 (used to give all-NaN)
    with pytest.raises(ValueError, match="Only 1 shared gene"):
        weighted_connectivity_score(one, lib1)


@pytest.mark.parametrize("n_genes", [1, 2, MIN_SHARED_GENES - 1])
def test_too_few_genes_rejected_by_both_scorers(n_genes):
    genes = [f"G{i}" for i in range(n_genes)]
    raw = pd.Series(np.linspace(-2, 2, n_genes) if n_genes > 1 else [2.0], index=genes)
    lib = _library().loc[genes]
    with pytest.raises(ValueError, match="shared gene"):
        cosine_reversal_score(raw, lib)
    dis = _disease().iloc[:n_genes].assign(logFC=raw.to_numpy())
    with pytest.raises(ValueError, match="shared gene"):
        weighted_connectivity_score(dis, lib)


def test_minimum_gene_count_is_accepted():
    genes = [f"G{i}" for i in range(MIN_SHARED_GENES)]
    dis = _disease().iloc[:MIN_SHARED_GENES].assign(logFC=np.linspace(-2, 2, MIN_SHARED_GENES))
    lib = _library().loc[genes]
    assert np.isfinite(cosine_reversal_score(zscore_disease_signature(dis), lib)).all()
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # small WTCS gene sets warn -- expected here
        assert np.isfinite(weighted_connectivity_score(dis, lib)).all()


# ---------------------------------------------------------------------------
# 5. Duplicate drug names
# ---------------------------------------------------------------------------
def _csv_text(header_drugs):
    rng = np.random.default_rng(7)
    rows = [",".join([g] + [f"{x:.4f}" for x in rng.normal(size=len(header_drugs))]) for g in GENES]
    return "gene," + ",".join(header_drugs) + "\n" + "\n".join(rows) + "\n"


@pytest.mark.parametrize("header", [["methotrexate", "methotrexate", "other"],
                                    ["Methotrexate", "methotrexate", "other"]])
def test_duplicate_drug_columns_rejected_at_load(tmp_path, header):
    """FIXED: pandas silently renamed the copy to 'methotrexate.1', which escaped the
    indication lookup and surfaced an already-indicated drug as a novel candidate."""
    text = _csv_text(header)
    path = tmp_path / "l1000.csv"
    path.write_text(text)
    for source in (str(path), path, io.StringIO(text), io.BytesIO(text.encode())):  # BytesIO ~ upload
        with pytest.raises(ValueError, match="Duplicate drug columns"):
            load_l1000_matrix(source)


def test_clean_upload_buffer_still_loads_fully():
    buf = io.BytesIO(_csv_text(["a", "b", "c"]).encode())
    df = load_l1000_matrix(buf)  # header peek must not consume the stream
    assert list(df.columns) == ["a", "b", "c"] and df.shape == (N_GENES, 3)


def test_duplicate_drug_columns_rejected_in_memory():
    lib = _library(dup=_reverser())
    lib.insert(len(lib.columns), "dup", np.random.default_rng(8).normal(size=N_GENES), allow_duplicates=True)
    for method in ("cosine", "wtcs"):
        with pytest.raises(ValueError, match="Duplicate drug names"):
            score_reversal(_disease(), lib, method=method)


@pytest.mark.parametrize("names", [["dup", "dup", "x"], ["Tofa", "tofa", "x"]])
def test_duplicate_names_in_scores_rejected_by_validation_and_candidates(names):
    """FIXED: validation kept the WORSE copy's rank, silently missing a recovery."""
    scores = pd.Series([-0.9, 0.1, 0.2], index=names)
    with pytest.raises(ValueError, match="Duplicate drug names"):
        check_recovery(scores, DISEASE, top_k=1, reference_set={names[0]})
    with pytest.raises(ValueError, match="Duplicate drug names"):
        screen_drugs(scores, {}, DISEASE)


# ---------------------------------------------------------------------------
# 6. Zero-variance disease signature
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("value", [1.5, 0.0, -3.0])
def test_zero_variance_signature_rejected(value):
    """FIXED: used to z-score to all-NaN -> NaN scores -> EVERY drug a candidate, and
    validation 'recovering' whichever drugs happened to come first."""
    dis, lib = _disease(logfc=np.full(N_GENES, value)), _library()
    with pytest.raises(ValueError, match="zero variance"):
        zscore_disease_signature(dis)
    for method in ("cosine", "wtcs"):
        with pytest.raises(ValueError, match="zero variance"):
            score_reversal(dis, lib, method=method)
    with pytest.raises(ValueError, match="zero variance"):
        cosine_reversal_score(pd.Series(value, index=GENES), lib)  # raw constant vector


def test_nan_scores_from_other_scorers_cannot_become_candidates():
    """Defense in depth: the dashboard's default fast path (app/fast_scoring.py) bypasses
    the src scorer checks, so the validation/candidates entry points reject NaN too."""
    from fast_scoring import cosine_reversal_score_fast
    nan_vec = pd.Series(np.nan, index=GENES)  # what a zero-variance z-score produced
    scores = cosine_reversal_score_fast(nan_vec, _library())
    assert scores.isna().all()
    with pytest.raises(ValueError, match="NaN/infinite reversal scores"):
        screen_drugs(scores, {}, DISEASE)
    with pytest.raises(ValueError, match="NaN/infinite reversal scores"):
        check_recovery(scores, DISEASE, top_k=2, reference_set={"noise_0"})


# ---------------------------------------------------------------------------
# 7. NaN / inf in the drug matrix
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("bad_value", [np.nan, np.inf, -np.inf])
@pytest.mark.parametrize("method", ["cosine", "wtcs"])
def test_non_finite_drug_values_rejected_naming_the_drug(method, bad_value):
    """FIXED: cosine gave a NaN score (drug then listed as a candidate and ranked last in
    validation); WTCS silently gave 0.0 for any drug with a single NaN gene."""
    lib = _library(good=_reverser())
    lib.loc["G7", "good"] = bad_value
    with pytest.raises(ValueError, match=r"1 drug\(s\) have NaN/infinite expression values.*good"):
        score_reversal(_disease(), lib, method=method)


def test_nan_outside_signature_genes_only_matters_for_wtcs():
    """Cosine only uses the disease genes; WTCS ranks every gene in the matrix."""
    lib = _library()
    lib.loc["EXTRA_GENE"] = 0.5
    lib.loc["EXTRA_GENE", "noise_1"] = np.nan
    dis = _disease()
    assert np.isfinite(score_reversal(dis, lib, method="cosine")).all()
    with pytest.raises(ValueError, match="noise_1"):
        score_reversal(dis, lib, method="wtcs")


def test_nan_scores_rejected_by_validation_and_candidates():
    scores = pd.Series([-0.8, np.nan, 0.3], index=["a", "b", "c"])
    with pytest.raises(ValueError, match="NaN/infinite reversal scores"):
        screen_drugs(scores, {}, DISEASE)
    with pytest.raises(ValueError, match="NaN/infinite reversal scores"):
        check_recovery(scores, DISEASE, top_k=1, reference_set={"a"})


# ---------------------------------------------------------------------------
# 8. Single drug in the library  (already handled -- regression guard)
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("method", ["cosine", "wtcs"])
def test_single_drug_library(method):
    lib = pd.DataFrame({"only": _reverser()}, index=GENES)
    scores = score_reversal(_disease(), lib, method=method)
    assert list(scores.index) == ["only"] and scores["only"] < 0

    cands = rank_repurposing_candidates(screen_drugs(scores, {}, DISEASE), top_n=20)  # top_n > pool
    assert list(cands["drug"]) == ["only"] and list(cands["candidate_rank"]) == [1]

    val = check_recovery(scores, DISEASE, top_k=20, reference_set={"only"})
    assert val["recovered_drugs"] == ["only"] and val["n_drugs_ranked"] == 1
    assert "1/1" in format_validation_statement(val)
    assert len(rank_candidates(scores, top_n=20)) == 1

    # same single drug, but already indicated: validation keeps it, candidates are empty
    cands_ind = rank_repurposing_candidates(screen_drugs(scores, {"only": {DISEASE}}, DISEASE), top_n=20)
    assert cands_ind.empty and "candidate_rank" in cands_ind.columns
    assert check_recovery(scores, DISEASE, top_k=20, reference_set={"only"})["recovered_count"] == 1


def test_single_non_reversing_drug_gives_empty_candidates_not_crash():
    lib = pd.DataFrame({"only": -_reverser()}, index=GENES)  # mimics the disease
    scores = score_reversal(_disease(), lib)
    screened = screen_drugs(scores, {}, DISEASE)
    assert screened["candidate_status"].tolist() == [STATUS_NOT_REVERSING]
    assert rank_repurposing_candidates(screened, top_n=20).empty


# ---------------------------------------------------------------------------
# 9. Indicated reverser tied with a non-indicated drug
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("indicated,novel", [("aa_indicated", "zz_novel"),   # indicated wins the tie-break
                                             ("zz_indicated", "aa_novel")])  # novel wins the tie-break
@pytest.mark.parametrize("method", ["cosine", "wtcs"])
def test_indicated_drug_tied_with_novel_drug(method, indicated, novel):
    col = _reverser()
    lib = _library(n_noise=10, **{indicated: col, novel: col})
    # TEST FIXTURE on placeholder names (not real indication data); mixed case on purpose
    indications = {indicated.upper(): {"Rheumatoid Arthritis"}}

    for cols in (list(lib.columns), list(lib.columns[::-1])):
        scores = score_reversal(_disease(), lib[cols], method=method)
        assert scores[indicated] == scores[novel], "test setup: the two drugs must tie"

        screened = screen_drugs(scores, indications, DISEASE).set_index("drug")
        assert screened.loc[indicated, "candidate_status"] == STATUS_INDICATED
        assert screened.loc[novel, "candidate_status"] == STATUS_CANDIDATE
        # tie broken by name -> fixed reversal ranks 1 and 2, independent of column order
        expected = {d: i + 1 for i, d in enumerate(sorted([indicated, novel]))}
        assert screened.loc[indicated, "reversal_rank"] == expected[indicated]
        assert screened.loc[novel, "reversal_rank"] == expected[novel]

        cands = rank_repurposing_candidates(screened.reset_index(), top_n=5)
        assert indicated not in set(cands["drug"])
        assert cands.iloc[0]["drug"] == novel and cands.iloc[0]["candidate_rank"] == 1

        val = check_recovery(scores, DISEASE, top_k=2, reference_set={indicated})
        assert val["recovered_drugs"] == [indicated]
        assert val["reference_ranks"] == {indicated: expected[indicated]}
