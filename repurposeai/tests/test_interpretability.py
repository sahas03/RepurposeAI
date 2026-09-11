"""
test_interpretability.py
Gene-level rationale must not depend on the GENE0000-style placeholder format or
on gene order, so it works unchanged when real gene symbols replace placeholders.

Uses synthetic values with deliberately NON-real labels in several formats
(mixed case / punctuation strings, integer IDs, shuffled order). No real gene data.

Run: python tests/test_interpretability.py   (or: pytest tests/)
"""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from interpretability import top_contributing_genes, explain_candidate

N = 60
rng = np.random.default_rng(3)
PLACEHOLDER = [f"GENE{i:04d}" for i in range(N)]
DISEASE = rng.normal(0, 1, N)
DRUGS = rng.normal(0, 1, (N, 4))
DRUGS[:, 0] = -DISEASE + rng.normal(0, 0.3, N)  # a reversal drug

LABEL_FORMATS = {
    "placeholder": PLACEHOLDER,
    "mixed-case/punctuation": [f"sym_{chr(97 + i % 26)}{i}-x.{i % 7}" for i in range(N)],
    "integer IDs": [int(1000 + 37 * i) for i in range(N)],
}


def _frames(labels, shuffle_seed=None):
    disease = pd.Series(DISEASE, index=labels)
    l1000 = pd.DataFrame(DRUGS, index=labels, columns=["d0", "d1", "d2", "d3"])
    if shuffle_seed is not None:  # different row order in each input
        disease = disease.sample(frac=1, random_state=shuffle_seed)
        l1000 = l1000.sample(frac=1, random_state=shuffle_seed + 1)
    return disease, l1000


def _canonical(df, labels):
    """Map labels back to placeholder names so outputs from different formats compare."""
    back = dict(zip(labels, PLACEHOLDER))
    return df.assign(gene=df["gene"].map(back))


def test_output_independent_of_label_format_and_order():
    base_d, base_l = _frames(PLACEHOLDER)
    base = top_contributing_genes(base_d, base_l["d0"], top_n=10)
    for name, labels in LABEL_FORMATS.items():
        for seed in (None, 11):
            d, l = _frames(labels, seed)
            out = _canonical(top_contributing_genes(d, l["d0"], top_n=10), labels)
            pd.testing.assert_frame_equal(out, base, check_dtype=False, obj=f"{name}, shuffle={seed}")

            exp = explain_candidate("d0", d, l, top_n_genes=10)
            assert exp["summary"].startswith("d0 most strongly reverses 10 of the top 10"), exp["summary"]


def test_no_overlap_raises_clear_error():
    d, _ = _frames(LABEL_FORMATS["mixed-case/punctuation"])
    _, l = _frames(LABEL_FORMATS["integer IDs"])
    try:
        top_contributing_genes(d, l["d0"])
    except ValueError as e:
        assert "No shared gene labels" in str(e)
    else:
        raise AssertionError("expected ValueError for disjoint gene IDs")


def test_duplicate_labels_raise():
    labels = PLACEHOLDER[:-1] + [PLACEHOLDER[0]]
    d, l = _frames(labels)
    try:
        top_contributing_genes(d, l["d0"])
    except ValueError as e:
        assert "duplicate gene labels" in str(e)
    else:
        raise AssertionError("expected ValueError for duplicate gene labels")


def test_nan_genes_dropped_not_mislabeled():
    d, l = _frames(PLACEHOLDER)
    drug = l["d0"].copy()
    drug.iloc[:5] = np.nan
    out = top_contributing_genes(d, drug, top_n=N)
    assert len(out) == N - 5 and out["contribution"].notna().all()


def test_fewer_genes_than_top_n():
    d, l = _frames(PLACEHOLDER)
    exp = explain_candidate("d0", d.iloc[:4], l, top_n_genes=10)
    assert len(exp["top_genes"]) == 4 and "of the top 4 " in exp["summary"]


def main():
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for t in tests:
        t()
        print(f"PASSED {t.__name__}")
    print(f"\nALL {len(tests)} INTERPRETABILITY TESTS PASSED")


if __name__ == "__main__":
    main()
